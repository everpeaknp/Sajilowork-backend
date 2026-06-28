"""
Email Management Models
"""
import uuid
from django.db import models
from django.conf import settings
from django.core.validators import EmailValidator
from django.utils import timezone


class EmailTemplate(models.Model):
    """Email template for various notification types"""
    
    TEMPLATE_TYPE_CHOICES = [
        ('transactional', 'Transactional'),
        ('notification', 'Notification'),
        ('marketing', 'Marketing'),
        ('system', 'System'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True, help_text="Template name")
    slug = models.SlugField(max_length=255, unique=True, help_text="Unique identifier")
    description = models.TextField(blank=True, help_text="Template description")
    
    # Template Type
    template_type = models.CharField(
        max_length=50, 
        choices=TEMPLATE_TYPE_CHOICES,
        default='notification',
        help_text="Type of email template"
    )
    
    # Content
    subject = models.CharField(max_length=255, help_text="Email subject line (supports variables)")
    html_content = models.TextField(help_text="HTML email body (supports variables)")
    text_content = models.TextField(blank=True, help_text="Plain text version")
    
    # Channel Configuration
    send_email = models.BooleanField(default=True, help_text="Send as email")
    send_in_app_notification = models.BooleanField(default=False, help_text="Send as in-app notification")
    send_push_notification = models.BooleanField(default=False, help_text="Send as push notification")
    
    # Status
    is_active = models.BooleanField(default=True, help_text="Is template active")
    
    # Metadata
    language_code = models.CharField(max_length=10, default='en', help_text="Language code (e.g., en, es)")
    template_group = models.CharField(max_length=100, null=True, blank=True, help_text="Group templates together")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='created_email_templates'
    )
    
    class Meta:
        db_table = 'email_templates'
        ordering = ['-created_at']
        verbose_name = 'Email Template'
        verbose_name_plural = 'Email Templates'
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['template_type', 'is_active']),
            models.Index(fields=['language_code']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.template_type})"


class EmailSetting(models.Model):
    """Global email settings and branding"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Company Branding
    company_name = models.CharField(max_length=255, default="Airtasker")
    company_logo = models.ImageField(upload_to='email/logos/', null=True, blank=True)
    support_email = models.EmailField(validators=[EmailValidator()])
    
    # Design Colors
    primary_color = models.CharField(max_length=7, default='#4F46E5', help_text="Hex color code")
    secondary_color = models.CharField(max_length=7, default='#10B981', help_text="Hex color code")
    
    # Footer Configuration
    footer_text = models.TextField(blank=True, default="© 2024 Airtasker. All rights reserved.")
    social_links = models.JSONField(default=dict, blank=True, help_text="Social media links")
    unsubscribe_url = models.URLField(blank=True, help_text="Unsubscribe page URL")
    
    # Global Toggles
    email_enabled = models.BooleanField(default=True, help_text="Master toggle for all emails")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'email_settings'
        verbose_name = 'Email Setting'
        verbose_name_plural = 'Email Settings'
    
    def __str__(self):
        return f"Email Settings - {self.company_name}"
    
    def save(self, *args, **kwargs):
        """Ensure only one settings instance exists"""
        if not self.pk and EmailSetting.objects.exists():
            # Update existing instead of creating new
            existing = EmailSetting.objects.first()
            self.pk = existing.pk
        return super().save(*args, **kwargs)


class SMTPConfiguration(models.Model):
    """SMTP server configuration"""
    
    ENCRYPTION_CHOICES = [
        ('tls', 'TLS'),
        ('ssl', 'SSL'),
        ('none', 'None'),
    ]
    
    PROVIDER_CHOICES = [
        ('gmail', 'Gmail'),
        ('outlook', 'Outlook'),
        ('sendgrid', 'SendGrid'),
        ('mailgun', 'Mailgun'),
        ('ses', 'Amazon SES'),
        ('custom', 'Custom SMTP'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # SMTP Details
    name = models.CharField(max_length=100, help_text="Configuration name")
    host = models.CharField(max_length=255, help_text="SMTP server host")
    port = models.IntegerField(default=587, help_text="SMTP server port")
    username = models.CharField(max_length=255, help_text="SMTP username")
    password = models.CharField(max_length=500, help_text="SMTP password (encrypted)")
    encryption = models.CharField(
        max_length=10, 
        choices=ENCRYPTION_CHOICES,
        default='tls',
        help_text="Encryption method"
    )
    
    # Email Headers
    from_email = models.EmailField(validators=[EmailValidator()], help_text="From email address")
    from_name = models.CharField(max_length=255, help_text="From name")
    
    # Provider
    provider = models.CharField(
        max_length=50, 
        choices=PROVIDER_CHOICES,
        default='custom',
        help_text="Email service provider"
    )
    
    # Status
    is_active = models.BooleanField(default=False, help_text="Active SMTP configuration")
    last_tested_at = models.DateTimeField(null=True, blank=True, help_text="Last connection test")
    test_status = models.CharField(max_length=20, null=True, blank=True, help_text="Test result")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'smtp_configurations'
        verbose_name = 'SMTP Configuration'
        verbose_name_plural = 'SMTP Configurations'
    
    def __str__(self):
        return f"{self.name} ({self.provider})"
    
    def save(self, *args, **kwargs):
        """Ensure only one active SMTP configuration; encrypt password at rest."""
        from apps.mails.smtp_manager import SMTPManager

        if self.password and not str(self.password).startswith('enc:'):
            self.password = SMTPManager.encrypt_password(self.password)
        if self.is_active:
            SMTPConfiguration.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        return super().save(*args, **kwargs)


class NotificationRule(models.Model):
    """Rules for when and how to send notifications"""
    
    CATEGORY_CHOICES = [
        ('account', 'Account'),
        ('jobs', 'Jobs'),
        ('projects', 'Projects'),
        ('tasks', 'Tasks'),
        ('services', 'Services'),
        ('messages', 'Messages'),
        ('payments', 'Payments'),
        ('marketing', 'Marketing'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Event Configuration
    event_name = models.CharField(
        max_length=100, 
        unique=True, 
        help_text="Unique event identifier (e.g., user.welcome)"
    )
    event_category = models.CharField(
        max_length=50, 
        choices=CATEGORY_CHOICES,
        help_text="Event category"
    )
    display_name = models.CharField(max_length=255, help_text="Human-readable name")
    description = models.TextField(blank=True, help_text="Event description")
    
    # Channel Toggles
    email_enabled = models.BooleanField(default=True, help_text="Send email notification")
    push_enabled = models.BooleanField(default=True, help_text="Send push notification")
    inapp_enabled = models.BooleanField(default=True, help_text="Send in-app notification")
    sms_enabled = models.BooleanField(default=False, help_text="Send SMS notification")
    
    # Recipient Types
    user_notification = models.BooleanField(default=True, help_text="Send to user")
    admin_notification = models.BooleanField(default=False, help_text="Send to admin")
    
    # Associated Template
    email_template = models.ForeignKey(
        'EmailTemplate', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='notification_rules',
        help_text="Email template to use"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification_rules'
        verbose_name = 'Notification Rule'
        verbose_name_plural = 'Notification Rules'
        ordering = ['event_category', 'event_name']
        indexes = [
            models.Index(fields=['event_name']),
            models.Index(fields=['event_category']),
        ]
    
    def __str__(self):
        return f"{self.display_name} ({self.event_name})"


class ContactSubmission(models.Model):
    """Contact form submissions"""
    
    STATUS_CHOICES = [
        ('new', 'New'),
        ('read', 'Read'),
        ('replied', 'Replied'),
        ('archived', 'Archived'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Contact Details
    name = models.CharField(max_length=255, help_text="Contact name")
    email = models.EmailField(validators=[EmailValidator()], help_text="Contact email")
    message = models.TextField(help_text="Contact message")
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='new',
        help_text="Submission status"
    )
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="Sender IP address")
    user_agent = models.CharField(max_length=500, blank=True, help_text="Browser user agent")
    
    # Response
    admin_notes = models.TextField(blank=True, help_text="Admin notes/response")
    responded_at = models.DateTimeField(null=True, blank=True, help_text="When admin responded")
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contact_responses'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'contact_submissions'
        ordering = ['-created_at']
        verbose_name = 'Contact Submission'
        verbose_name_plural = 'Contact Submissions'
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['email']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"Contact from {self.name} ({self.email}) - {self.status}"
    
    def mark_as_read(self):
        """Mark submission as read"""
        if self.status == 'new':
            self.status = 'read'
            self.save(update_fields=['status', 'updated_at'])
    
    def mark_as_replied(self, admin_user):
        """Mark submission as replied"""
        self.status = 'replied'
        self.responded_at = timezone.now()
        self.responded_by = admin_user
        self.save(update_fields=['status', 'responded_at', 'responded_by', 'updated_at'])


class EmailLog(models.Model):
    """Log of sent emails with delivery tracking"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('opened', 'Opened'),
        ('clicked', 'Clicked'),
        ('bounced', 'Bounced'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Recipient
    recipient_email = models.EmailField(validators=[EmailValidator()])
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='received_emails'
    )
    
    # Email Details
    subject = models.CharField(max_length=500)
    html_content = models.TextField()
    text_content = models.TextField(blank=True)
    
    # Template Reference
    template_used = models.ForeignKey(
        'EmailTemplate', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='email_logs'
    )
    
    # Delivery Status
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Email delivery status"
    )
    
    # Tracking Timestamps
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    bounced_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    
    # Error Information
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0, help_text="Number of retry attempts")
    
    # External IDs
    external_id = models.CharField(
        max_length=255, 
        blank=True, 
        help_text="Provider message ID"
    )
    smtp_config_used = models.ForeignKey(
        'SMTPConfiguration', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='email_logs'
    )
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional data")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'email_logs'
        ordering = ['-created_at']
        verbose_name = 'Email Log'
        verbose_name_plural = 'Email Logs'
        indexes = [
            models.Index(fields=['recipient_email', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['-sent_at']),
            models.Index(fields=['external_id']),
        ]
    
    def __str__(self):
        return f"Email to {self.recipient_email} - {self.status}"
    
    def mark_as_sent(self):
        """Mark email as sent"""
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save(update_fields=['status', 'sent_at', 'updated_at'])
    
    def mark_as_delivered(self):
        """Mark email as delivered"""
        self.status = 'delivered'
        self.delivered_at = timezone.now()
        self.save(update_fields=['status', 'delivered_at', 'updated_at'])
    
    def mark_as_opened(self):
        """Mark email as opened"""
        self.status = 'opened'
        self.opened_at = timezone.now()
        self.save(update_fields=['status', 'opened_at', 'updated_at'])
    
    def mark_as_clicked(self):
        """Mark email as clicked"""
        self.status = 'clicked'
        self.clicked_at = timezone.now()
        self.save(update_fields=['status', 'clicked_at', 'updated_at'])
    
    def mark_as_failed(self, error_message=''):
        """Mark email as failed"""
        self.status = 'failed'
        self.failed_at = timezone.now()
        self.error_message = error_message
        self.retry_count += 1
        self.save(update_fields=['status', 'failed_at', 'error_message', 'retry_count', 'updated_at'])
