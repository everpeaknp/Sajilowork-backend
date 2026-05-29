"""
Notification Service
Handles multi-channel notification delivery (in-app, email, push, SMS)
"""
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
import logging

from .models import Notification, NotificationPreference

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Central service for sending notifications through multiple channels.
    
    Channels:
    - In-app notifications (always created)
    - Email notifications (if user preference enabled)
    - Push notifications (if user preference enabled)
    - SMS notifications (if user preference enabled)
    """
    
    @staticmethod
    def send_notification(
        user,
        notification_type: str,
        title: str,
        message: str,
        related_object=None,
        data: dict = None,
        priority: str = 'medium',
        sender=None,
    ) -> Notification:
        """
        Send notification to user through all enabled channels.
        
        Args:
            user: User to notify
            notification_type: Type of notification (e.g., 'bid_accepted')
            title: Notification title
            message: Notification message
            related_object: Optional related model instance
            data: Optional additional data (dict)
            priority: Priority level ('low', 'normal', 'high', 'urgent')
            
        Returns:
            Notification: Created notification object
        """
        try:
            # Per-type channel preferences (one row per user + notification_type)
            prefs, _created = NotificationPreference.objects.get_or_create(
                user=user,
                notification_type=notification_type,
                defaults={
                    'in_app_enabled': True,
                    'email_enabled': True,
                    'push_enabled': True,
                    'sms_enabled': False,
                    'instant': True,
                },
            )
            
            # Create in-app notification (always created)
            notification = Notification.objects.create(
                recipient=user,
                sender=sender,
                notification_type=notification_type,
                title=title,
                message=message,
                content_type=ContentType.objects.get_for_model(related_object.__class__) if related_object else None,
                object_id=related_object.id if related_object else None,
                data=data or {},
                action_url=(data or {}).get('action_url', ''),
                priority=priority,
                is_read=False,
            )
            
            logger.info(f"Created in-app notification {notification.id} for user {user.id}")

            # Secondary channels must not roll back in-app notification or caller transactions
            if prefs.email_enabled and NotificationService._should_send_email(notification_type, prefs):
                try:
                    NotificationService._queue_email_notification(notification)
                except Exception as e:
                    logger.warning(f"Email notification queue skipped: {e}")

            if prefs.push_enabled and NotificationService._should_send_push(notification_type, prefs):
                try:
                    NotificationService._queue_push_notification(notification)
                except Exception as e:
                    logger.warning(f"Push notification queue skipped: {e}")

            if prefs.sms_enabled and priority == 'urgent':
                try:
                    NotificationService._queue_sms_notification(notification)
                except Exception as e:
                    logger.warning(f"SMS notification queue skipped: {e}")

            try:
                NotificationService._send_websocket_notification(notification)
            except Exception as e:
                logger.warning(f"WebSocket notification skipped: {e}")

            return notification

        except Exception as e:
            logger.error(f"Error sending notification: {e}", exc_info=True)
            raise
    
    @staticmethod
    def _should_send_email(_notification_type: str, prefs: NotificationPreference) -> bool:
        """Check if email should be sent for this notification type."""
        return prefs.email_enabled

    @staticmethod
    def _should_send_push(_notification_type: str, prefs: NotificationPreference) -> bool:
        """Check if push notification should be sent for this notification type."""
        return prefs.push_enabled
    
    @staticmethod
    def _queue_email_notification(notification: Notification):
        """Queue email notification for async delivery."""
        from django.conf import settings

        # Avoid extra DB work inside hot paths while using SQLite in local dev
        if settings.DEBUG:
            return

        try:
            # Import here to avoid circular imports
            from .tasks import send_email_notification
            
            # Queue Celery task
            send_email_notification.delay(str(notification.id))
            logger.info(f"Queued email notification {notification.id}")
            
        except ImportError:
            logger.warning("Celery tasks not available, email notification not queued")
        except Exception as e:
            logger.error(f"Error queuing email notification: {e}")
    
    @staticmethod
    def _queue_push_notification(notification: Notification):
        """Queue push notification for async delivery."""
        try:
            # Import here to avoid circular imports
            from .tasks import send_push_notification
            
            # Queue Celery task
            send_push_notification.delay(str(notification.id))
            logger.info(f"Queued push notification {notification.id}")
            
        except ImportError:
            logger.warning("Celery tasks not available, push notification not queued")
        except Exception as e:
            logger.error(f"Error queuing push notification: {e}")
    
    @staticmethod
    def _queue_sms_notification(notification: Notification):
        """Queue SMS notification for async delivery."""
        try:
            # Import here to avoid circular imports
            from .tasks import send_sms_notification
            
            # Queue Celery task
            send_sms_notification.delay(str(notification.id))
            logger.info(f"Queued SMS notification {notification.id}")
            
        except ImportError:
            logger.warning("Celery tasks not available, SMS notification not queued")
        except Exception as e:
            logger.error(f"Error queuing SMS notification: {e}")
    
    @staticmethod
    def _send_websocket_notification(notification: Notification):
        """Send real-time WebSocket notification."""
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            from .serializers import NotificationSerializer
            
            channel_layer = get_channel_layer()
            
            if channel_layer:
                # Send to user's notification channel
                async_to_sync(channel_layer.group_send)(
                    f'notifications_{notification.recipient_id}',
                    {
                        'type': 'notification_message',
                        'notification': NotificationSerializer(notification).data
                    }
                )
                logger.info(f"Sent WebSocket notification {notification.id}")
            else:
                logger.warning("Channel layer not available, WebSocket notification not sent")
                
        except ImportError:
            logger.warning("Channels not available, WebSocket notification not sent")
        except Exception as e:
            logger.error(f"Error sending WebSocket notification: {e}")
    
    @staticmethod
    def mark_as_read(notification_id: str, user):
        """Mark notification as read."""
        try:
            notification = Notification.objects.get(id=notification_id, recipient=user)
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save()
            
            logger.info(f"Marked notification {notification_id} as read")
            return notification
            
        except Notification.DoesNotExist:
            logger.error(f"Notification {notification_id} not found for user {user.id}")
            raise
    
    @staticmethod
    def mark_all_as_read(user):
        """Mark all notifications as read for a user."""
        count = Notification.objects.filter(
            recipient=user,
            is_read=False
        ).update(
            is_read=True,
            read_at=timezone.now()
        )
        
        logger.info(f"Marked {count} notifications as read for user {user.id}")
        return count
    
    @staticmethod
    def delete_notification(notification_id: str, user):
        """Delete a notification."""
        try:
            notification = Notification.objects.get(id=notification_id, recipient=user)
            notification.delete()
            
            logger.info(f"Deleted notification {notification_id}")
            return True
            
        except Notification.DoesNotExist:
            logger.error(f"Notification {notification_id} not found for user {user.id}")
            raise
    
    @staticmethod
    def get_unread_count(user) -> int:
        """Get count of unread notifications for a user."""
        return Notification.objects.filter(recipient=user, is_read=False).count()
    
    @staticmethod
    def get_recent_notifications(user, limit: int = 10):
        """Get recent notifications for a user."""
        return Notification.objects.filter(recipient=user).order_by('-created_at')[:limit]
    
    @staticmethod
    @transaction.atomic
    def send_bulk_notification(
        users: list,
        notification_type: str,
        title: str,
        message: str,
        data: dict = None
    ) -> int:
        """
        Send notification to multiple users.
        
        Args:
            users: List of User objects
            notification_type: Type of notification
            title: Notification title
            message: Notification message
            data: Optional additional data
            
        Returns:
            int: Number of notifications created
        """
        notifications = []
        
        for user in users:
            try:
                notification = NotificationService.send_notification(
                    user=user,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    data=data
                )
                notifications.append(notification)
            except Exception as e:
                logger.error(f"Error sending notification to user {user.id}: {e}")
                continue
        
        logger.info(f"Sent {len(notifications)} bulk notifications")
        return len(notifications)
