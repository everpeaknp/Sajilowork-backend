"""
Business logic services for chat app.
"""
from django.db.models import Q, Count, Max, Prefetch
from django.utils import timezone
from .models import Conversation, Message, TypingIndicator, ConversationMute


class ChatService:
    """Service class for chat-related business logic."""
    
    @staticmethod
    def get_or_create_conversation(user1, user2, task=None, bid=None):
        """
        Get or create a conversation between two users.
        
        Args:
            user1: First user
            user2: Second user
            task: Optional task object
            bid: Optional bid object
        
        Returns:
            Conversation object
        """
        from .conversation_resolver import get_or_create_conversation as resolve

        conversation, _created = resolve(
            task=task,
            bid=bid,
            participant_users=[user1, user2],
        )
        return conversation
    
    @staticmethod
    def get_user_conversations(user, include_archived=False):
        """
        Get all conversations for a user with unread counts.
        
        Args:
            user: User object
            include_archived: Whether to include archived conversations
        
        Returns:
            QuerySet of conversations
        """
        queryset = Conversation.objects.filter(
            participants=user,
            is_active=True
        ).prefetch_related(
            'participants',
            Prefetch(
                'messages',
                queryset=Message.objects.filter(is_deleted=False).order_by('-created_at')
            )
        ).annotate(
            unread_count=Count(
                'messages',
                filter=Q(messages__is_read=False) & ~Q(messages__sender=user)
            )
        )
        
        if not include_archived:
            queryset = queryset.filter(is_archived=False)
        
        return queryset.order_by('-last_message_at', '-created_at')
    
    @staticmethod
    def send_message(conversation, sender, content, message_type='text', attachment=None, reply_to=None):
        """
        Send a message in a conversation.
        
        Args:
            conversation: Conversation object
            sender: User sending the message
            content: Message content
            message_type: Type of message (text, image, file, system)
            attachment: Optional file attachment
            reply_to: Optional message being replied to
        
        Returns:
            Message object
        """
        # Create message
        message = Message.objects.create(
            conversation=conversation,
            sender=sender,
            content=content,
            message_type=message_type,
            attachment=attachment,
            reply_to=reply_to
        )
        
        # Update conversation's last_message_at
        conversation.last_message_at = timezone.now()
        conversation.save(update_fields=['last_message_at'])
        
        # Remove typing indicator if exists
        TypingIndicator.objects.filter(
            conversation=conversation,
            user=sender
        ).delete()
        
        return message
    
    @staticmethod
    def mark_conversation_as_read(conversation, user):
        """
        Mark all messages in a conversation as read for a user.
        
        Args:
            conversation: Conversation object
            user: User marking messages as read
        """
        Message.objects.filter(
            conversation=conversation,
            is_read=False
        ).exclude(sender=user).update(
            is_read=True,
            read_at=timezone.now()
        )
    
    @staticmethod
    def get_conversation_messages(conversation, user, limit=50, before_message_id=None):
        """
        Get messages from a conversation with pagination.
        
        Args:
            conversation: Conversation object
            user: User requesting messages
            limit: Number of messages to return
            before_message_id: Get messages before this message ID (for pagination)
        
        Returns:
            QuerySet of messages
        """
        queryset = Message.objects.filter(
            conversation=conversation,
            is_deleted=False
        ).select_related('sender', 'reply_to__sender')
        
        if before_message_id:
            # Get messages before the specified message (for pagination)
            before_message = Message.objects.get(id=before_message_id)
            queryset = queryset.filter(created_at__lt=before_message.created_at)
        
        return queryset.order_by('-created_at')[:limit]
    
    @staticmethod
    def is_conversation_muted(conversation, user):
        """
        Check if a conversation is muted for a user.
        
        Args:
            conversation: Conversation object
            user: User to check
        
        Returns:
            Boolean indicating if conversation is muted
        """
        mute = ConversationMute.objects.filter(
            conversation=conversation,
            user=user
        ).first()
        
        if not mute:
            return False
        
        return mute.is_muted()
    
    @staticmethod
    def mute_conversation(conversation, user, muted_until=None):
        """
        Mute a conversation for a user.
        
        Args:
            conversation: Conversation object
            user: User muting the conversation
            muted_until: Optional datetime until which conversation is muted (None = forever)
        
        Returns:
            ConversationMute object
        """
        mute, created = ConversationMute.objects.update_or_create(
            conversation=conversation,
            user=user,
            defaults={'muted_until': muted_until}
        )
        return mute
    
    @staticmethod
    def unmute_conversation(conversation, user):
        """
        Unmute a conversation for a user.
        
        Args:
            conversation: Conversation object
            user: User unmuting the conversation
        """
        ConversationMute.objects.filter(
            conversation=conversation,
            user=user
        ).delete()
    
    @staticmethod
    def get_unread_message_count(user):
        """
        Get total unread message count for a user across all conversations.
        
        Args:
            user: User object
        
        Returns:
            Integer count of unread messages
        """
        return Message.objects.filter(
            conversation__participants=user,
            is_read=False,
            is_deleted=False
        ).exclude(sender=user).count()
    
    @staticmethod
    def search_messages(user, query, conversation=None):
        """
        Search messages for a user.
        
        Args:
            user: User searching
            query: Search query string
            conversation: Optional conversation to limit search to
        
        Returns:
            QuerySet of matching messages
        """
        queryset = Message.objects.filter(
            conversation__participants=user,
            is_deleted=False,
            content__icontains=query
        ).select_related('sender', 'conversation')
        
        if conversation:
            queryset = queryset.filter(conversation=conversation)
        
        return queryset.order_by('-created_at')
    
    @staticmethod
    def get_conversation_stats(conversation):
        """
        Get statistics for a conversation.
        
        Args:
            conversation: Conversation object
        
        Returns:
            Dictionary with conversation statistics
        """
        total_messages = conversation.messages.filter(is_deleted=False).count()
        
        # Get message counts by type
        message_types = conversation.messages.filter(
            is_deleted=False
        ).values('message_type').annotate(count=Count('id'))
        
        # Get participant message counts
        participant_counts = conversation.messages.filter(
            is_deleted=False
        ).values('sender__id', 'sender__first_name', 'sender__last_name').annotate(
            count=Count('id')
        )
        
        return {
            'total_messages': total_messages,
            'message_types': {item['message_type']: item['count'] for item in message_types},
            'participant_counts': list(participant_counts),
            'created_at': conversation.created_at,
            'last_message_at': conversation.last_message_at,
        }
