"""
WebSocket Consumers for Real-Time Chat
Handles WebSocket connections for live messaging, typing indicators, and presence
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone
from asgiref.sync import sync_to_async

from .models import Conversation, Message, TypingIndicator
from .messaging_policy import conversation_allows_messaging
from .services import ChatService

User = get_user_model()
logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time chat functionality.
    
    Features:
    - Real-time message delivery
    - Typing indicators
    - Read receipts
    - Online presence
    - Message reactions
    """
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope['user']
        
        # Reject unauthenticated users
        if not self.user.is_authenticated:
            await self.close(code=4001)
            return
        
        # Get conversation ID from URL
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'
        
        # Verify user has access to this conversation
        has_access = await self.verify_conversation_access()
        if not has_access:
            await self.close(code=4003)
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Notify others that user is online
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_online',
                'user_id': str(self.user.id),
                'user_name': self.user.get_full_name(),
            }
        )
        
        logger.info(f"User {self.user.id} connected to conversation {self.conversation_id}")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if hasattr(self, 'room_group_name'):
            # Notify others that user is offline
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_offline',
                    'user_id': str(self.user.id),
                }
            )
            
            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            
            # Clear typing indicator
            await self.clear_typing_indicator()
            
            logger.info(f"User {self.user.id} disconnected from conversation {self.conversation_id}")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'chat_message':
                await self.handle_chat_message(data)
            elif message_type == 'typing_start':
                await self.handle_typing_start()
            elif message_type == 'typing_stop':
                await self.handle_typing_stop()
            elif message_type == 'mark_read':
                await self.handle_mark_read(data)
            elif message_type == 'message_reaction':
                await self.handle_message_reaction(data)
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {text_data}")
            await self.send_error("Invalid message format")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await self.send_error("Error processing message")
    
    async def handle_chat_message(self, data):
        """Handle new chat message"""
        message_text = (data.get('content') or data.get('message') or '').strip()
        attachments = data.get('attachments', [])
        
        if not message_text and not attachments:
            await self.send_error("Message cannot be empty")
            return

        can_send, deny_reason = await self.check_messaging_allowed()
        if not can_send:
            await self.send_error(deny_reason or "Messaging is not available for this task.")
            return
        
        # Create message in database
        message = await self.create_message(message_text, attachments)
        
        if message:
            # Clear typing indicator
            await self.clear_typing_indicator()
            
            # Broadcast message to room
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': await self.serialize_message(message),
                }
            )
    
    async def handle_typing_start(self):
        """Handle typing indicator start"""
        await self.set_typing_indicator(True)
        
        # Broadcast typing indicator
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'user_id': str(self.user.id),
                'user_name': self.user.get_full_name(),
                'is_typing': True,
            }
        )
    
    async def handle_typing_stop(self):
        """Handle typing indicator stop"""
        await self.clear_typing_indicator()
        
        # Broadcast typing stopped
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'user_id': str(self.user.id),
                'is_typing': False,
            }
        )
    
    async def handle_mark_read(self, data):
        """Handle mark messages as read"""
        message_ids = data.get('message_ids', [])
        
        if message_ids:
            await self.mark_messages_read(message_ids)
            
            # Broadcast read receipt
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'read_receipt',
                    'user_id': str(self.user.id),
                    'message_ids': message_ids,
                }
            )
    
    async def handle_message_reaction(self, data):
        """Handle message reaction (like, love, etc.)"""
        message_id = data.get('message_id')
        reaction_type = data.get('reaction')
        
        if message_id and reaction_type:
            await self.add_message_reaction(message_id, reaction_type)
            
            # Broadcast reaction
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_reaction',
                    'message_id': message_id,
                    'user_id': str(self.user.id),
                    'reaction': reaction_type,
                }
            )
    
    # ========================================================================
    # Event Handlers (called by channel_layer.group_send)
    # ========================================================================
    
    async def chat_message(self, event):
        """Send chat message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message'],
        }))
    
    async def typing_indicator(self, event):
        """Send typing indicator to WebSocket"""
        # Don't send typing indicator to the user who is typing
        if event['user_id'] != str(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'typing_indicator',
                'user_id': event['user_id'],
                'user_name': event.get('user_name'),
                'is_typing': event['is_typing'],
            }))
    
    async def read_receipt(self, event):
        """Send read receipt to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'read_receipt',
            'user_id': event['user_id'],
            'message_ids': event['message_ids'],
        }))
    
    async def message_reaction(self, event):
        """Send message reaction to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'message_reaction',
            'message_id': event['message_id'],
            'user_id': event['user_id'],
            'reaction': event['reaction'],
        }))
    
    async def user_online(self, event):
        """Send user online status to WebSocket"""
        # Don't send to the user who just came online
        if event['user_id'] != str(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'user_online',
                'user_id': event['user_id'],
                'user_name': event['user_name'],
            }))
    
    async def user_offline(self, event):
        """Send user offline status to WebSocket"""
        # Don't send to the user who just went offline
        if event['user_id'] != str(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'user_offline',
                'user_id': event['user_id'],
            }))
    
    # ========================================================================
    # Database Operations
    # ========================================================================
    
    @database_sync_to_async
    def verify_conversation_access(self):
        """Verify user has access to conversation"""
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            return conversation.participants.filter(id=self.user.id).exists()
        except Conversation.DoesNotExist:
            return False

    @database_sync_to_async
    def check_messaging_allowed(self):
        try:
            conversation = Conversation.objects.select_related('task', 'bid', 'bid__task').get(
                id=self.conversation_id
            )
            return conversation_allows_messaging(conversation)
        except Conversation.DoesNotExist:
            return False, 'Conversation not found.'
    
    @database_sync_to_async
    def create_message(self, message_text, attachments):
        """Create message in database"""
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)

            message = Message.objects.create(
                conversation=conversation,
                sender=self.user,
                content=message_text,
                message_type='text' if not attachments else 'file',
            )

            conversation.last_message_at = timezone.now()
            conversation.save(update_fields=['last_message_at'])

            return message
        except Exception as e:
            logger.error(f"Error creating message: {e}")
            return None

    @database_sync_to_async
    def serialize_message(self, message):
        """Serialize message for WebSocket (same shape as MessageBriefSerializer)."""
        from django.http import HttpRequest
        from rest_framework.request import Request
        from .serializers import MessageBriefSerializer

        http_request = HttpRequest()
        http_request.user = self.user
        drf_request = Request(http_request)
        return MessageBriefSerializer(message, context={'request': drf_request}).data
    
    @database_sync_to_async
    def set_typing_indicator(self, is_typing):
        """Set typing indicator in database."""
        if not is_typing:
            return
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            TypingIndicator.objects.update_or_create(
                conversation=conversation,
                user=self.user,
                defaults={'started_at': timezone.now()},
            )
        except Exception as e:
            logger.error(f"Error setting typing indicator: {e}")
    
    @database_sync_to_async
    def clear_typing_indicator(self):
        """Clear typing indicator"""
        try:
            TypingIndicator.objects.filter(
                conversation_id=self.conversation_id,
                user=self.user
            ).delete()
        except Exception as e:
            logger.error(f"Error clearing typing indicator: {e}")
    
    @database_sync_to_async
    def mark_messages_read(self, message_ids):
        """Mark messages as read"""
        try:
            Message.objects.filter(
                id__in=message_ids,
                conversation_id=self.conversation_id
            ).exclude(
                sender=self.user
            ).update(
                is_read=True,
                read_at=timezone.now()
            )
        except Exception as e:
            logger.error(f"Error marking messages read: {e}")
    
    @database_sync_to_async
    def add_message_reaction(self, message_id, reaction_type):
        """Add reaction to message"""
        try:
            from .models import MessageReaction
            
            message = Message.objects.get(id=message_id)
            MessageReaction.objects.update_or_create(
                message=message,
                user=self.user,
                defaults={'reaction_type': reaction_type}
            )
        except Exception as e:
            logger.error(f"Error adding reaction: {e}")
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    async def send_error(self, error_message):
        """Send error message to client"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': error_message,
        }))


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications.
    
    Features:
    - Real-time notification delivery
    - Notification count updates
    - Mark as read functionality
    """
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope['user']
        
        # Reject unauthenticated users
        if not self.user.is_authenticated:
            await self.close(code=4001)
            return
        
        # User-specific notification channel
        self.room_group_name = f'notifications_{self.user.id}'
        
        # Join notification group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send current unread count
        unread_count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': unread_count,
        }))
        
        logger.info(f"User {self.user.id} connected to notifications")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            logger.info(f"User {self.user.id} disconnected from notifications")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'mark_read':
                notification_id = data.get('notification_id')
                if notification_id:
                    await self.mark_notification_read(notification_id)
            elif message_type == 'mark_all_read':
                await self.mark_all_notifications_read()
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {text_data}")
        except Exception as e:
            logger.error(f"Error handling notification message: {e}")
    
    # Event handlers
    async def new_notification(self, event):
        """Send new notification to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'new_notification',
            'notification': event['notification'],
        }))
    
    async def unread_count(self, event):
        """Send unread count update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': event['count'],
        }))
    
    # Database operations
    @database_sync_to_async
    def get_unread_count(self):
        """Get unread notification count"""
        from apps.notifications.models import Notification
        return Notification.objects.filter(
            user=self.user,
            is_read=False
        ).count()
    
    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """Mark single notification as read"""
        from apps.notifications.models import Notification
        try:
            Notification.objects.filter(
                id=notification_id,
                user=self.user
            ).update(is_read=True, read_at=timezone.now())
        except Exception as e:
            logger.error(f"Error marking notification read: {e}")
    
    @database_sync_to_async
    def mark_all_notifications_read(self):
        """Mark all notifications as read"""
        from apps.notifications.models import Notification
        try:
            Notification.objects.filter(
                user=self.user,
                is_read=False
            ).update(is_read=True, read_at=timezone.now())
        except Exception as e:
            logger.error(f"Error marking all notifications read: {e}")
