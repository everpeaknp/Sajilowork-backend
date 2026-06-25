"""
Email Service - Core business logic for email management
"""
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
from typing import Dict, Any, Optional, List
import logging

from .models import (
    EmailTemplate,
    EmailSetting,
    SMTPConfiguration,
    NotificationRule,
    EmailLog
)
from .template_parser import TemplateParser

User = get_user_model()
logger = logging.getLogger(__name__)


class EmailService:
    """
    Core service for sending and managing emails.
    Integrates with existing notification system.
    """
    
    @classmethod
    def send_email(
        cls,
        event_name: str,
        recipient: User,
        context: Dict[str, Any],
        force_send: bool = False
    ) -> Optional[EmailLog]:
        """
        Send email for a specific event using template system.
        
        Args:
            event_name: Event identifier (e.g., 'user.welcome', 'task.assigned')
            recipient: User to send email to
            context: Template variables
            force_send: Skip all checks and send immediately
            
        Returns:
            EmailLog object if email was sent, None otherwise
        """
        try:
            # 1. Check global email toggle
            if not force_send:
                email_settings = EmailSetting.objects.first()
                if not email_settings or not email_settings.email_enabled:
                    logger.info("Emails globally disabled, skipping send")
                    return None
            
            # 2. Get notification rule for this event
            if not force_send:
                notification_rule = NotificationRule.objects.filter(
                    event_name=event_name,
                    email_enabled=True
                ).first()
                
                if not notification_rule:
                    logger.info(f"No notification rule found for event: {event_name}")
                    return None
                
                if not notification_rule.email_template:
                    logger.info(f"No email template assigned to rule: {event_name}")
                    return None
                
                template = notification_rule.email_template
            else:
                # For force_send, try to get template directly
                template = EmailTemplate.objects.filter(
                    slug=event_name,
                    is_active=True
                ).first()
                
                if not template:
                    logger.error(f"Template not found for event: {event_name}")
                    return None
            
            # 3. Check template is active
            if not template.is_active or not template.send_email:
                logger.info(f"Template inactive or email disabled: {template.name}")
                return None
            
            # 4. Get active SMTP configuration
            smtp_config = SMTPConfiguration.objects.filter(is_active=True).first()
            if not smtp_config:
                logger.error("No active SMTP configuration found")
                return None
            
            # 5. Add global settings to context
            email_settings = EmailSetting.objects.first()
            if email_settings:
                context.update({
                    'company_name': email_settings.company_name,
                    'support_email': email_settings.support_email,
                    'primary_color': email_settings.primary_color,
                    'secondary_color': email_settings.secondary_color,
                    'footer_text': email_settings.footer_text,
                    'unsubscribe_url': email_settings.unsubscribe_url,
                })
            
            # 6. Parse template content
            try:
                subject = TemplateParser.parse(template.subject, context)
                html_content = TemplateParser.parse(template.html_content, context)
                text_content = TemplateParser.parse(template.text_content, context) if template.text_content else ""
            except Exception as e:
                logger.error(f"Error parsing template: {e}")
                return None
            
            # 7. Create email log entry
            email_log = EmailLog.objects.create(
                recipient_email=recipient.email,
                recipient_user=recipient,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                template_used=template,
                smtp_config_used=smtp_config,
                status='pending'
            )
            
            logger.info(f"Created email log {email_log.id} for {recipient.email}")
            
            # 8. Queue Celery task for async sending
            try:
                from .tasks import send_email_task
                send_email_task.delay(str(email_log.id))
                logger.info(f"Queued email task for log {email_log.id}")
            except ImportError:
                logger.warning("Celery tasks not available, email not queued")
            except Exception as e:
                logger.error(f"Error queuing email task: {e}")
            
            return email_log
            
        except Exception as e:
            logger.error(f"Error in send_email: {e}", exc_info=True)
            return None
    
    @classmethod
    def send_test_email(
        cls,
        template_id: str,
        recipient_email: str,
        context: Dict[str, Any] = None
    ) -> EmailLog:
        """
        Send a test email with provided or sample context.
        
        Args:
            template_id: Template UUID
            recipient_email: Email address to send to
            context: Optional context (uses sample if not provided)
            
        Returns:
            EmailLog object
            
        Raises:
            EmailTemplate.DoesNotExist: If template not found
        """
        template = EmailTemplate.objects.get(id=template_id)
        
        # Use sample context if none provided
        if context is None:
            context = TemplateParser.build_sample_context()
        
        # Add global settings
        email_settings = EmailSetting.objects.first()
        if email_settings:
            context.update({
                'company_name': email_settings.company_name,
                'support_email': email_settings.support_email,
            })
        
        # Parse template
        subject = TemplateParser.parse(template.subject, context)
        html_content = TemplateParser.parse(template.html_content, context)
        text_content = TemplateParser.parse(template.text_content, context) if template.text_content else ""
        
        # Get SMTP config
        smtp_config = SMTPConfiguration.objects.filter(is_active=True).first()
        if not smtp_config:
            raise Exception("No active SMTP configuration")
        
        # Create log
        email_log = EmailLog.objects.create(
            recipient_email=recipient_email,
            subject=f"[TEST] {subject}",
            html_content=html_content,
            text_content=text_content,
            template_used=template,
            smtp_config_used=smtp_config,
            status='pending',
            metadata={'is_test': True}
        )
        
        # Queue task
        try:
            from .tasks import send_email_task
            send_email_task.delay(str(email_log.id))
        except ImportError:
            logger.warning("Celery not available for test email")
        
        return email_log
    
    @classmethod
    def send_batch_email(
        cls,
        template_id: str,
        recipients: List[User],
        context: Dict[str, Any]
    ) -> int:
        """
        Send email to multiple recipients.
        
        Args:
            template_id: Template UUID
            recipients: List of User objects
            context: Shared template context
            
        Returns:
            Number of emails queued
        """
        template = EmailTemplate.objects.get(id=template_id)
        
        if not template.is_active:
            raise Exception("Template is not active")
        
        count = 0
        for recipient in recipients:
            try:
                # Create personalized context
                recipient_context = context.copy()
                recipient_context.update({
                    'user_name': recipient.get_full_name() or recipient.email,
                    'user_email': recipient.email,
                    'user_first_name': recipient.first_name,
                    'user_last_name': recipient.last_name,
                })
                
                # Send email
                email_log = cls.send_email(
                    event_name=template.slug,
                    recipient=recipient,
                    context=recipient_context,
                    force_send=True
                )
                
                if email_log:
                    count += 1
                    
            except Exception as e:
                logger.error(f"Error sending batch email to {recipient.email}: {e}")
                continue
        
        return count
    
    @classmethod
    def preview_template(
        cls,
        template_id: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, str]:
        """
        Generate preview of template with context.
        
        Args:
            template_id: Template UUID
            context: Optional context (uses sample if not provided)
            
        Returns:
            Dictionary with 'subject', 'html_preview', 'text_preview'
        """
        template = EmailTemplate.objects.get(id=template_id)
        
        if context is None:
            context = TemplateParser.build_sample_context()
        
        # Add global settings
        email_settings = EmailSetting.objects.first()
        if email_settings:
            context.update({
                'company_name': email_settings.company_name,
                'support_email': email_settings.support_email,
            })
        
        subject = TemplateParser.parse(template.subject, context)
        html_preview = TemplateParser.parse(template.html_content, context)
        text_preview = TemplateParser.parse(template.text_content, context) if template.text_content else ""
        
        return {
            'subject': subject,
            'html_preview': html_preview,
            'text_preview': text_preview
        }
    
    @classmethod
    def track_email_open(cls, email_log_id: str) -> bool:
        """
        Track email open event.
        
        Args:
            email_log_id: EmailLog UUID
            
        Returns:
            True if tracked successfully
        """
        try:
            email_log = EmailLog.objects.get(id=email_log_id)
            email_log.mark_as_opened()
            logger.info(f"Tracked email open for log {email_log_id}")
            return True
        except EmailLog.DoesNotExist:
            logger.error(f"Email log {email_log_id} not found")
            return False
    
    @classmethod
    def track_email_click(cls, email_log_id: str, link: str = None) -> bool:
        """
        Track email link click event.
        
        Args:
            email_log_id: EmailLog UUID
            link: Optional clicked link URL
            
        Returns:
            True if tracked successfully
        """
        try:
            email_log = EmailLog.objects.get(id=email_log_id)
            email_log.mark_as_clicked()
            
            if link:
                # Store clicked link in metadata
                metadata = email_log.metadata or {}
                clicks = metadata.get('clicks', [])
                clicks.append({
                    'link': link,
                    'clicked_at': timezone.now().isoformat()
                })
                metadata['clicks'] = clicks
                email_log.metadata = metadata
                email_log.save(update_fields=['metadata'])
            
            logger.info(f"Tracked email click for log {email_log_id}")
            return True
        except EmailLog.DoesNotExist:
            logger.error(f"Email log {email_log_id} not found")
            return False
    
    @classmethod
    def get_email_statistics(
        cls,
        start_date=None,
        end_date=None
    ) -> Dict[str, Any]:
        """
        Get email statistics for date range.
        
        Args:
            start_date: Start date (default: 30 days ago)
            end_date: End date (default: now)
            
        Returns:
            Dictionary with email statistics
        """
        if end_date is None:
            end_date = timezone.now()
        if start_date is None:
            start_date = end_date - timezone.timedelta(days=30)
        
        logs = EmailLog.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        total_sent = logs.count()
        delivered = logs.filter(status='delivered').count()
        opened = logs.filter(status='opened').count()
        clicked = logs.filter(status='clicked').count()
        failed = logs.filter(status='failed').count()
        bounced = logs.filter(status='bounced').count()
        
        # Calculate rates
        open_rate = (opened / delivered * 100) if delivered > 0 else 0
        click_rate = (clicked / opened * 100) if opened > 0 else 0
        bounce_rate = (bounced / total_sent * 100) if total_sent > 0 else 0
        delivery_rate = (delivered / total_sent * 100) if total_sent > 0 else 0
        
        return {
            'total_sent': total_sent,
            'delivered': delivered,
            'opened': opened,
            'clicked': clicked,
            'failed': failed,
            'bounced': bounced,
            'open_rate': round(open_rate, 2),
            'click_rate': round(click_rate, 2),
            'bounce_rate': round(bounce_rate, 2),
            'delivery_rate': round(delivery_rate, 2),
        }


class TemplateService:
    """Service for template management operations"""
    
    @classmethod
    def create_template(cls, data: Dict[str, Any], created_by: User) -> EmailTemplate:
        """Create new email template"""
        data['created_by'] = created_by
        template = EmailTemplate.objects.create(**data)
        logger.info(f"Created template {template.id}: {template.name}")
        return template
    
    @classmethod
    def update_template(cls, template_id: str, data: Dict[str, Any]) -> EmailTemplate:
        """Update existing template"""
        template = EmailTemplate.objects.get(id=template_id)
        
        for key, value in data.items():
            setattr(template, key, value)
        
        template.save()
        logger.info(f"Updated template {template.id}: {template.name}")
        return template
    
    @classmethod
    def clone_template(cls, template_id: str, new_name: str, created_by: User) -> EmailTemplate:
        """Clone existing template"""
        original = EmailTemplate.objects.get(id=template_id)
        
        # Create copy
        cloned = EmailTemplate.objects.create(
            name=new_name,
            slug=f"{original.slug}-copy",
            description=f"Copy of {original.name}",
            template_type=original.template_type,
            subject=original.subject,
            html_content=original.html_content,
            text_content=original.text_content,
            send_email=original.send_email,
            send_in_app_notification=original.send_in_app_notification,
            send_push_notification=original.send_push_notification,
            is_active=False,  # Clones start inactive
            language_code=original.language_code,
            template_group=original.template_group,
            created_by=created_by
        )
        
        logger.info(f"Cloned template {original.id} to {cloned.id}")
        return cloned
    
    @classmethod
    def validate_template(cls, html_content: str) -> tuple[bool, str]:
        """Validate template HTML"""
        return TemplateParser.validate(html_content)


class AnalyticsService:
    """Service for email analytics"""
    
    @classmethod
    def get_dashboard_stats(cls, start_date=None, end_date=None) -> Dict[str, Any]:
        """Get complete dashboard statistics"""
        return EmailService.get_email_statistics(start_date, end_date)
    
    @classmethod
    def get_template_performance(cls, template_id: str) -> Dict[str, Any]:
        """Get performance metrics for specific template"""
        logs = EmailLog.objects.filter(template_used_id=template_id)
        
        total_sent = logs.count()
        delivered = logs.filter(status='delivered').count()
        opened = logs.filter(status='opened').count()
        clicked = logs.filter(status='clicked').count()
        
        return {
            'total_sent': total_sent,
            'delivered': delivered,
            'opened': opened,
            'clicked': clicked,
            'open_rate': round((opened / delivered * 100) if delivered > 0 else 0, 2),
            'click_rate': round((clicked / opened * 100) if opened > 0 else 0, 2),
        }
