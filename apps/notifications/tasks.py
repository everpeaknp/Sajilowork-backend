"""
Celery Tasks for Notifications
Background jobs for email, SMS, and push notifications
"""
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_email_notification(self, notification_id: str):
    """
    Send email notification.
    
    Args:
        notification_id: Notification ID
    """
    from .models import Notification
    
    try:
        notification = Notification.objects.get(id=notification_id)
        user = notification.recipient
        
        # Check if user has email
        if not user.email:
            logger.warning(f"User {user.id} has no email address")
            return {'success': False, 'error': 'No email address'}
        
        # Email templates based on notification type
        subject_templates = {
            'bid_accepted': 'Your Bid Has Been Accepted!',
            'bid_rejected': 'Bid Update',
            'bid_received': 'New Bid Received',
            'task_started': 'Task Started',
            'task_completed': 'Task Completed',
            'task_approved': 'Task Approved - Payment Released',
            'message_received': 'New Message',
            'payment_received': 'Payment Received',
            'payment_sent': 'Payment Sent',
            'review_received': 'New Review Received',
        }
        
        subject = subject_templates.get(
            notification.notification_type,
            'SajiloWork Notification'
        )
        
        # Create email content
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4F46E5; color: white; padding: 20px; text-align: center; }}
                .content {{ background-color: #f9f9f9; padding: 20px; }}
                .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
                .button {{ display: inline-block; padding: 12px 24px; background-color: #4F46E5; color: white; text-decoration: none; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>SajiloWork</h1>
                </div>
                <div class="content">
                    <h2>{notification.title}</h2>
                    <p>{notification.message}</p>
                    <p style="margin-top: 20px;">
                        <a href="{settings.FRONTEND_URL}" class="button">View on SajiloWork</a>
                    </p>
                </div>
                <div class="footer">
                    <p>This is an automated email from SajiloWork. Please do not reply.</p>
                    <p>&copy; 2024 SajiloWork. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        plain_message = strip_tags(html_message)
        
        # Send email
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Sent email notification {notification_id} to {user.email}")
        return {'success': True}
        
    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found")
        return {'success': False, 'error': 'Notification not found'}
    except Exception as exc:
        logger.error(f"Error sending email notification: {exc}")
        raise self.retry(exc=exc, countdown=300)  # Retry after 5 minutes


@shared_task(bind=True, max_retries=3)
def send_sms_notification(self, notification_id: str):
    """
    Send SMS notification via Nepal SMS gateway.
    
    Args:
        notification_id: Notification ID
    """
    from .models import Notification
    import requests
    
    try:
        notification = Notification.objects.get(id=notification_id)
        user = notification.recipient
        
        # Check if user has phone number
        if not user.phone_number:
            logger.warning(f"User {user.id} has no phone number")
            return {'success': False, 'error': 'No phone number'}
        
        # SMS message (max 160 characters)
        sms_message = f"SajiloWork: {notification.title}. {notification.message[:100]}"
        
        # Nepal SMS Gateway Configuration
        # Popular options: Sparrow SMS, Aakash SMS, SMS Nepal
        sms_api_url = settings.SMS_GATEWAY_URL
        sms_api_token = settings.SMS_GATEWAY_TOKEN
        
        if not sms_api_url or not sms_api_token:
            logger.warning("SMS gateway not configured")
            return {'success': False, 'error': 'SMS gateway not configured'}
        
        # Send SMS via API (example for Sparrow SMS)
        response = requests.post(
            sms_api_url,
            json={
                'token': sms_api_token,
                'from': 'SajiloWork',
                'to': str(user.phone_number),
                'text': sms_message
            },
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info(f"Sent SMS notification {notification_id} to {user.phone_number}")
            return {'success': True}
        else:
            logger.error(f"SMS API error: {response.text}")
            return {'success': False, 'error': response.text}
        
    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found")
        return {'success': False, 'error': 'Notification not found'}
    except Exception as exc:
        logger.error(f"Error sending SMS notification: {exc}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, max_retries=3)
def send_push_notification(self, notification_id: str):
    """
    Send push notification to mobile devices.
    
    Args:
        notification_id: Notification ID
    """
    from .models import Notification
    
    try:
        notification = Notification.objects.get(id=notification_id)
        user = notification.recipient
        
        # Get user's device tokens (FCM tokens)
        # This would require a DeviceToken model
        # For now, we'll log the attempt
        
        logger.info(f"Push notification {notification_id} queued for user {user.id}")
        
        # TODO: Implement Firebase Cloud Messaging (FCM) integration
        # from firebase_admin import messaging
        # 
        # message = messaging.Message(
        #     notification=messaging.Notification(
        #         title=notification.title,
        #         body=notification.message,
        #     ),
        #     token=device_token,
        # )
        # 
        # response = messaging.send(message)
        
        return {'success': True, 'note': 'Push notifications not yet implemented'}
        
    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found")
        return {'success': False, 'error': 'Notification not found'}
    except Exception as exc:
        logger.error(f"Error sending push notification: {exc}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True)
def batch_send_notifications(self, user_ids: list, notification_type: str, title: str, message: str):
    """
    Send notifications to multiple users in batch.
    
    Args:
        user_ids: List of user IDs
        notification_type: Type of notification
        title: Notification title
        message: Notification message
    """
    from apps.users.models import User
    from .services import NotificationService
    
    try:
        users = User.objects.filter(id__in=user_ids)
        
        sent_count = 0
        for user in users:
            try:
                NotificationService.send_notification(
                    user=user,
                    notification_type=notification_type,
                    title=title,
                    message=message
                )
                sent_count += 1
            except Exception as e:
                logger.error(f"Error sending notification to user {user.id}: {e}")
                continue
        
        logger.info(f"Batch sent {sent_count} notifications")
        return {
            'success': True,
            'sent_count': sent_count,
            'total_users': len(user_ids)
        }
        
    except Exception as e:
        logger.error(f"Error in batch_send_notifications: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(bind=True)
def send_welcome_email(self, user_id: str):
    """
    Send welcome email to new user.
    
    Args:
        user_id: User ID
    """
    from apps.users.models import User
    
    try:
        user = User.objects.get(id=user_id)
        
        if not user.email:
            return {'success': False, 'error': 'No email address'}
        
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4F46E5; color: white; padding: 30px; text-align: center; }}
                .content {{ background-color: #f9f9f9; padding: 30px; }}
                .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
                .button {{ display: inline-block; padding: 12px 24px; background-color: #4F46E5; color: white; text-decoration: none; border-radius: 5px; margin: 10px 5px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to SajiloWork!</h1>
                </div>
                <div class="content">
                    <h2>Hi {user.first_name},</h2>
                    <p>Welcome to SajiloWork - Nepal's premier marketplace for getting things done!</p>
                    <p>Whether you're looking to:</p>
                    <ul>
                        <li><strong>Post a task</strong> and get help from skilled taskers</li>
                        <li><strong>Earn money</strong> by completing tasks in your area</li>
                    </ul>
                    <p>We're here to help you succeed.</p>
                    <p style="margin-top: 30px;">
                        <a href="{settings.FRONTEND_URL}/post-task" class="button">Post Your First Task</a>
                        <a href="{settings.FRONTEND_URL}/taskmap" class="button">Browse Tasks</a>
                    </p>
                    <p style="margin-top: 30px;">
                        <strong>Need help getting started?</strong><br>
                        Check out our <a href="{settings.FRONTEND_URL}/help">Help Center</a> or contact our support team.
                    </p>
                </div>
                <div class="footer">
                    <p>&copy; 2024 SajiloWork. All rights reserved.</p>
                    <p>Kathmandu, Nepal</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject='Welcome to SajiloWork!',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Sent welcome email to {user.email}")
        return {'success': True}
        
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return {'success': False, 'error': 'User not found'}
    except Exception as e:
        logger.error(f"Error sending welcome email: {e}")
        return {'success': False, 'error': str(e)}
