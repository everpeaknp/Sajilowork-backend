"""
Celery Tasks for Email Management
Async email sending and processing
"""
from celery import shared_task
from django.utils import timezone
from django.conf import settings
import logging

from .models import EmailLog, SMTPConfiguration
from .smtp_manager import SMTPManager

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_task(self, email_log_id: str):
    """
    Celery task to send email asynchronously.
    
    Args:
        email_log_id: UUID of EmailLog entry
        
    Returns:
        dict with status and message
    """
    try:
        # Get email log
        email_log = EmailLog.objects.get(id=email_log_id)
        
        # Get SMTP configuration
        smtp_config = email_log.smtp_config_used
        if not smtp_config:
            # Fallback to active SMTP config
            smtp_config = SMTPConfiguration.objects.filter(is_active=True).first()
            
            if not smtp_config:
                raise Exception("No active SMTP configuration found")
            
            email_log.smtp_config_used = smtp_config
            email_log.save(update_fields=['smtp_config_used'])
        
        # Send email via SMTP
        success, message = SMTPManager.send_email(
            smtp_config=smtp_config,
            to_email=email_log.recipient_email,
            subject=email_log.subject,
            html_content=email_log.html_content,
            text_content=email_log.text_content
        )
        
        if success:
            # Mark as sent
            email_log.mark_as_sent()
            
            logger.info(f"Email sent successfully: {email_log_id}")
            return {
                'status': 'success',
                'email_log_id': email_log_id,
                'message': 'Email sent successfully'
            }
        else:
            # Mark as failed
            email_log.mark_as_failed(error_message=message)
            
            logger.error(f"Email send failed: {email_log_id} - {message}")
            
            # Retry if under max retries
            if email_log.retry_count < 3:
                raise self.retry(exc=Exception(message), countdown=60 * email_log.retry_count)
            
            return {
                'status': 'failed',
                'email_log_id': email_log_id,
                'message': message
            }
    
    except EmailLog.DoesNotExist:
        logger.error(f"EmailLog not found: {email_log_id}")
        return {
            'status': 'error',
            'email_log_id': email_log_id,
            'message': 'Email log not found'
        }
    
    except Exception as e:
        logger.error(f"Error in send_email_task: {e}", exc_info=True)
        
        try:
            email_log = EmailLog.objects.get(id=email_log_id)
            email_log.mark_as_failed(error_message=str(e))
            
            # Retry
            if email_log.retry_count < 3:
                raise self.retry(exc=e, countdown=60 * email_log.retry_count)
                
        except Exception:
            pass
        
        return {
            'status': 'error',
            'email_log_id': email_log_id,
            'message': str(e)
        }


@shared_task
def send_batch_emails_task(batch_id: str):
    """
    Send emails in batch (for future batch email feature).
    
    Args:
        batch_id: UUID of email batch
        
    Returns:
        dict with statistics
    """
    # TODO: Implement batch email sending
    # Will be implemented in Phase 6 (Batch Operations)
    logger.info(f"Batch email task called for batch: {batch_id}")
    return {
        'status': 'pending',
        'batch_id': batch_id,
        'message': 'Batch email sending not yet implemented'
    }


@shared_task
def process_scheduled_emails():
    """
    Process scheduled emails (for future scheduling feature).
    Runs periodically via Celery Beat.
    
    Returns:
        dict with count of processed emails
    """
    # TODO: Implement scheduled email processing
    # Will be implemented in Phase 6 (Scheduled Emails)
    logger.info("Processing scheduled emails")
    return {
        'status': 'success',
        'processed': 0,
        'message': 'Scheduled emails not yet implemented'
    }


@shared_task
def cleanup_old_logs(days: int = 90):
    """
    Clean up old email logs (optional maintenance task).
    
    Args:
        days: Delete logs older than this many days
        
    Returns:
        dict with count of deleted logs
    """
    try:
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        
        # Only delete successfully sent/delivered emails older than cutoff
        deleted_count, _ = EmailLog.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['delivered', 'opened', 'clicked']
        ).delete()
        
        logger.info(f"Cleaned up {deleted_count} old email logs")
        
        return {
            'status': 'success',
            'deleted_count': deleted_count,
            'cutoff_date': cutoff_date.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up logs: {e}", exc_info=True)
        return {
            'status': 'error',
            'message': str(e)
        }


@shared_task
def sync_email_status(email_log_id: str):
    """
    Sync email delivery status from email provider (for future feature).
    
    Args:
        email_log_id: UUID of EmailLog entry
        
    Returns:
        dict with sync status
    """
    # TODO: Implement status syncing with email providers
    # Will integrate with SendGrid/Mailgun webhooks in Phase 6
    logger.info(f"Email status sync called for: {email_log_id}")
    return {
        'status': 'pending',
        'email_log_id': email_log_id,
        'message': 'Status syncing not yet implemented'
    }


@shared_task
def update_email_analytics():
    """
    Update email analytics cache (for future optimization).
    Runs periodically via Celery Beat.
    
    Returns:
        dict with update status
    """
    # TODO: Implement analytics caching
    # Will be implemented in Phase 7 (Performance Optimization)
    logger.info("Updating email analytics cache")
    return {
        'status': 'success',
        'message': 'Analytics caching not yet implemented'
    }
