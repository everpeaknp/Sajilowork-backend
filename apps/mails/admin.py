"""
Django Admin configuration for Email Management
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    EmailTemplate,
    EmailSetting,
    SMTPConfiguration,
    NotificationRule,
    EmailLog
)


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'template_type', 'is_active', 'channel_display', 'created_at']
    list_filter = ['template_type', 'is_active', 'send_email', 'language_code', 'created_at']
    search_fields = ['name', 'slug', 'subject', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at', 'created_by']
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'template_type', 'language_code', 'template_group')
        }),
        ('Email Content', {
            'fields': ('subject', 'html_content', 'text_content')
        }),
        ('Channel Configuration', {
            'fields': ('send_email', 'send_in_app_notification', 'send_push_notification')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def channel_display(self, obj):
        channels = []
        if obj.send_email:
            channels.append('📧 Email')
        if obj.send_in_app_notification:
            channels.append('📱 In-App')
        if obj.send_push_notification:
            channels.append('🔔 Push')
        return ', '.join(channels) if channels else 'None'
    channel_display.short_description = 'Channels'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(EmailSetting)
class EmailSettingAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'support_email', 'email_enabled', 'updated_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Company Branding', {
            'fields': ('company_name', 'company_logo', 'support_email')
        }),
        ('Design Colors', {
            'fields': ('primary_color', 'secondary_color')
        }),
        ('Footer Configuration', {
            'fields': ('footer_text', 'social_links', 'unsubscribe_url')
        }),
        ('Global Controls', {
            'fields': ('email_enabled',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        # Only allow one settings object
        return not EmailSetting.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion of settings
        return False


@admin.register(SMTPConfiguration)
class SMTPConfigurationAdmin(admin.ModelAdmin):
    list_display = ['name', 'provider', 'host', 'port', 'is_active', 'status_display', 'last_tested_at']
    list_filter = ['provider', 'is_active', 'encryption']
    search_fields = ['name', 'host', 'from_email']
    readonly_fields = ['id', 'last_tested_at', 'test_status', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'provider')
        }),
        ('SMTP Details', {
            'fields': ('host', 'port', 'username', 'password', 'encryption')
        }),
        ('Email Headers', {
            'fields': ('from_email', 'from_name')
        }),
        ('Status', {
            'fields': ('is_active', 'last_tested_at', 'test_status')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_display(self, obj):
        if obj.test_status == 'success':
            return format_html('<span style="color: green;">✓ Success</span>')
        elif obj.test_status == 'failed':
            return format_html('<span style="color: red;">✗ Failed</span>')
        else:
            return format_html('<span style="color: gray;">Not Tested</span>')
    status_display.short_description = 'Test Status'
    
    def has_delete_permission(self, request, obj=None):
        # Only superusers can delete SMTP configs
        return request.user.is_superuser


@admin.register(NotificationRule)
class NotificationRuleAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'event_name', 'event_category', 'channel_status', 'email_template']
    list_filter = ['event_category', 'email_enabled', 'push_enabled', 'inapp_enabled']
    search_fields = ['event_name', 'display_name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Event Information', {
            'fields': ('event_name', 'event_category', 'display_name', 'description')
        }),
        ('Channel Toggles', {
            'fields': ('email_enabled', 'push_enabled', 'inapp_enabled', 'sms_enabled')
        }),
        ('Recipient Configuration', {
            'fields': ('user_notification', 'admin_notification')
        }),
        ('Email Template', {
            'fields': ('email_template',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def channel_status(self, obj):
        status = []
        if obj.email_enabled:
            status.append('📧')
        if obj.push_enabled:
            status.append('🔔')
        if obj.inapp_enabled:
            status.append('📱')
        if obj.sms_enabled:
            status.append('💬')
        return ' '.join(status) if status else 'None'
    channel_status.short_description = 'Active Channels'


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ['recipient_email', 'subject_short', 'status_display', 'template_used', 'sent_at', 'opened_display']
    list_filter = ['status', 'sent_at', 'created_at']
    search_fields = ['recipient_email', 'subject', 'external_id']
    readonly_fields = [
        'id', 'recipient_email', 'recipient_user', 'subject', 'html_content', 
        'text_content', 'template_used', 'status', 'sent_at', 'delivered_at',
        'opened_at', 'clicked_at', 'bounced_at', 'failed_at', 'error_message',
        'retry_count', 'external_id', 'smtp_config_used', 'metadata',
        'created_at', 'updated_at'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Recipient', {
            'fields': ('recipient_email', 'recipient_user')
        }),
        ('Email Content', {
            'fields': ('subject', 'html_content', 'text_content')
        }),
        ('Template & Configuration', {
            'fields': ('template_used', 'smtp_config_used')
        }),
        ('Delivery Status', {
            'fields': ('status', 'sent_at', 'delivered_at', 'opened_at', 'clicked_at', 'bounced_at', 'failed_at')
        }),
        ('Error Information', {
            'fields': ('error_message', 'retry_count')
        }),
        ('External Tracking', {
            'fields': ('external_id', 'metadata')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def subject_short(self, obj):
        return obj.subject[:50] + '...' if len(obj.subject) > 50 else obj.subject
    subject_short.short_description = 'Subject'
    
    def status_display(self, obj):
        colors = {
            'pending': 'gray',
            'sent': 'blue',
            'delivered': 'green',
            'opened': 'darkgreen',
            'clicked': 'purple',
            'bounced': 'orange',
            'failed': 'red',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def opened_display(self, obj):
        if obj.opened_at:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: gray;">—</span>')
    opened_display.short_description = 'Opened'
    
    def has_add_permission(self, request):
        # Email logs are created automatically
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Only superusers can delete logs
        return request.user.is_superuser
