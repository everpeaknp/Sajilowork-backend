"""
Notifications App Admin
"""
from django.contrib import admin
from .models import (
    Notification, NotificationPreference, EmailNotification,
    PushNotification, DeviceToken, NotificationTemplate, NotificationBatch
)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin interface for Notification model"""
    list_display = [
        'id', 'recipient', 'sender', 'notification_type', 'title',
        'priority', 'is_read', 'is_archived', 'created_at'
    ]
    list_filter = [
        'notification_type', 'priority', 'is_read', 'is_archived', 'created_at'
    ]
    search_fields = ['recipient__email', 'sender__email', 'title', 'message']
    readonly_fields = ['id', 'created_at', 'updated_at', 'sent_at', 'read_at', 'archived_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'recipient', 'sender', 'notification_type', 'priority')
        }),
        ('Content', {
            'fields': ('title', 'message', 'action_url', 'data')
        }),
        ('Related Object', {
            'fields': ('content_type', 'object_id'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_read', 'read_at', 'is_archived', 'archived_at', 'is_sent', 'sent_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Allow staff to create in-app notifications manually."""
        return bool(request.user and request.user.is_staff)


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    """Admin interface for NotificationPreference model"""
    list_display = [
        'id', 'user', 'notification_type', 'in_app_enabled',
        'email_enabled', 'push_enabled', 'sms_enabled'
    ]
    list_filter = [
        'notification_type', 'in_app_enabled', 'email_enabled',
        'push_enabled', 'sms_enabled', 'instant', 'daily_digest', 'weekly_digest'
    ]
    search_fields = ['user__email', 'notification_type']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'user', 'notification_type')
        }),
        ('Channel Preferences', {
            'fields': ('in_app_enabled', 'email_enabled', 'push_enabled', 'sms_enabled')
        }),
        ('Frequency Settings', {
            'fields': ('instant', 'daily_digest', 'weekly_digest')
        }),
        ('Quiet Hours', {
            'fields': ('quiet_hours_enabled', 'quiet_hours_start', 'quiet_hours_end'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(EmailNotification)
class EmailNotificationAdmin(admin.ModelAdmin):
    """Admin interface for EmailNotification model"""
    list_display = [
        'id', 'recipient_email', 'subject', 'status',
        'sent_at', 'delivered_at', 'opened_at', 'retry_count'
    ]
    list_filter = ['status', 'sent_at', 'delivered_at']
    search_fields = ['recipient_email', 'subject', 'external_id']
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'sent_at', 'delivered_at',
        'opened_at', 'clicked_at', 'failed_at'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'notification', 'recipient_email', 'subject')
        }),
        ('Content', {
            'fields': ('body_text', 'body_html'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': (
                'status', 'sent_at', 'delivered_at', 'opened_at',
                'clicked_at', 'failed_at'
            )
        }),
        ('Error Tracking', {
            'fields': ('error_message', 'retry_count', 'max_retries'),
            'classes': ('collapse',)
        }),
        ('External Tracking', {
            'fields': ('external_id',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PushNotification)
class PushNotificationAdmin(admin.ModelAdmin):
    """Admin interface for PushNotification model"""
    list_display = [
        'id', 'platform', 'title', 'status',
        'sent_at', 'delivered_at', 'clicked_at', 'retry_count'
    ]
    list_filter = ['platform', 'status', 'sent_at', 'delivered_at']
    search_fields = ['title', 'body', 'device_token', 'external_id']
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'sent_at', 'delivered_at',
        'clicked_at', 'failed_at'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'notification', 'device_token', 'platform')
        }),
        ('Content', {
            'fields': ('title', 'body', 'data')
        }),
        ('Status', {
            'fields': (
                'status', 'sent_at', 'delivered_at', 'clicked_at', 'failed_at'
            )
        }),
        ('Error Tracking', {
            'fields': ('error_message', 'retry_count', 'max_retries'),
            'classes': ('collapse',)
        }),
        ('External Tracking', {
            'fields': ('external_id',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    """Admin interface for DeviceToken model"""
    list_display = [
        'id', 'user', 'platform', 'device_name',
        'is_active', 'last_used_at', 'created_at'
    ]
    list_filter = ['platform', 'is_active', 'created_at']
    search_fields = ['user__email', 'token', 'device_name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_used_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'user', 'token', 'platform', 'device_name')
        }),
        ('Status', {
            'fields': ('is_active', 'last_used_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    """Admin interface for NotificationTemplate model"""
    list_display = [
        'id', 'name', 'notification_type', 'channel', 'is_active', 'created_at'
    ]
    list_filter = ['notification_type', 'channel', 'is_active', 'created_at']
    search_fields = ['name', 'notification_type']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'notification_type', 'channel', 'is_active')
        }),
        ('Templates', {
            'fields': (
                'subject_template', 'title_template',
                'body_template', 'html_template'
            )
        }),
        ('Variables', {
            'fields': ('variables',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(NotificationBatch)
class NotificationBatchAdmin(admin.ModelAdmin):
    """Admin interface for NotificationBatch model"""
    list_display = [
        'id', 'name', 'notification_type', 'status',
        'recipient_count', 'sent_count', 'failed_count',
        'scheduled_at', 'created_at'
    ]
    list_filter = ['status', 'notification_type', 'scheduled_at', 'created_at']
    search_fields = ['name', 'notification_type']
    readonly_fields = [
        'id', 'sent_count', 'failed_count', 'started_at',
        'completed_at', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'notification_type', 'status')
        }),
        ('Recipients', {
            'fields': ('recipient_count', 'recipients_data')
        }),
        ('Template', {
            'fields': ('template', 'template_data')
        }),
        ('Progress', {
            'fields': ('sent_count', 'failed_count')
        }),
        ('Scheduling', {
            'fields': ('scheduled_at', 'started_at', 'completed_at')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
