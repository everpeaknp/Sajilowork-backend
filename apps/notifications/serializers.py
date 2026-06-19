"""
Notifications App Serializers
"""
from rest_framework import serializers
from .models import (
    Notification, NotificationPreference, EmailNotification,
    PushNotification, DeviceToken, NotificationTemplate, NotificationBatch,
    TaskAlertKeyword
)
from apps.users.serializers import UserListSerializer


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model"""
    sender = UserListSerializer(read_only=True)
    recipient = UserListSerializer(read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'recipient', 'sender', 'notification_type', 'title', 'message',
            'priority', 'content_type', 'object_id', 'data', 'action_url',
            'is_read', 'read_at', 'is_archived', 'archived_at',
            'is_sent', 'sent_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'recipient', 'sender', 'is_sent', 'sent_at',
            'read_at', 'archived_at', 'created_at', 'updated_at'
        ]


class NotificationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for notification lists"""
    sender_name = serializers.CharField(source='sender.get_full_name', read_only=True)
    sender_avatar = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'title', 'message', 'priority',
            'sender_name', 'sender_avatar', 'action_url',
            'is_read', 'is_archived', 'created_at'
        ]

    def get_sender_avatar(self, obj):
        from apps.users.user_media_utils import resolve_user_media_url

        sender = getattr(obj, 'sender', None)
        return resolve_user_media_url(
            self.context.get('request'),
            getattr(sender, 'profile_image', None) if sender else None,
        )


class NotificationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating notifications"""
    
    class Meta:
        model = Notification
        fields = [
            'recipient', 'sender', 'notification_type', 'title', 'message',
            'priority', 'content_type', 'object_id', 'data', 'action_url'
        ]
    
    def create(self, validated_data):
        """Create notification and trigger delivery"""
        notification = Notification.objects.create(**validated_data)
        # TODO: Trigger notification delivery via Celery
        return notification


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for NotificationPreference model"""
    
    class Meta:
        model = NotificationPreference
        fields = [
            'id', 'user', 'notification_type',
            'in_app_enabled', 'email_enabled', 'push_enabled', 'sms_enabled',
            'instant', 'daily_digest', 'weekly_digest',
            'quiet_hours_enabled', 'quiet_hours_start', 'quiet_hours_end',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class NotificationPreferenceUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating notification preferences"""
    
    class Meta:
        model = NotificationPreference
        fields = [
            'in_app_enabled', 'email_enabled', 'push_enabled', 'sms_enabled',
            'instant', 'daily_digest', 'weekly_digest',
            'quiet_hours_enabled', 'quiet_hours_start', 'quiet_hours_end'
        ]


class EmailNotificationSerializer(serializers.ModelSerializer):
    """Serializer for EmailNotification model"""
    
    class Meta:
        model = EmailNotification
        fields = [
            'id', 'notification', 'recipient_email', 'subject',
            'body_text', 'body_html', 'status', 'sent_at', 'delivered_at',
            'opened_at', 'clicked_at', 'failed_at', 'error_message',
            'retry_count', 'max_retries', 'external_id',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'sent_at', 'delivered_at', 'opened_at', 'clicked_at',
            'failed_at', 'created_at', 'updated_at'
        ]


class PushNotificationSerializer(serializers.ModelSerializer):
    """Serializer for PushNotification model"""
    
    class Meta:
        model = PushNotification
        fields = [
            'id', 'notification', 'device_token', 'platform',
            'title', 'body', 'data', 'status', 'sent_at', 'delivered_at',
            'clicked_at', 'failed_at', 'error_message', 'retry_count',
            'max_retries', 'external_id', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'sent_at', 'delivered_at', 'clicked_at', 'failed_at',
            'created_at', 'updated_at'
        ]


class DeviceTokenSerializer(serializers.ModelSerializer):
    """Serializer for DeviceToken model"""
    
    class Meta:
        model = DeviceToken
        fields = [
            'id', 'user', 'token', 'platform', 'device_name',
            'is_active', 'last_used_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'last_used_at', 'created_at', 'updated_at']


class DeviceTokenCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating device tokens"""
    
    class Meta:
        model = DeviceToken
        fields = ['token', 'platform', 'device_name']
    
    def create(self, validated_data):
        """Create or update device token"""
        user = self.context['request'].user
        token = validated_data['token']
        
        # Deactivate old tokens for this device
        DeviceToken.objects.filter(
            user=user,
            token=token
        ).update(is_active=False)
        
        # Create new token
        device_token = DeviceToken.objects.create(
            user=user,
            **validated_data
        )
        return device_token


class NotificationTemplateSerializer(serializers.ModelSerializer):
    """Serializer for NotificationTemplate model"""
    
    class Meta:
        model = NotificationTemplate
        fields = [
            'id', 'name', 'notification_type', 'channel',
            'subject_template', 'title_template', 'body_template',
            'html_template', 'variables', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class NotificationBatchSerializer(serializers.ModelSerializer):
    """Serializer for NotificationBatch model"""
    template = NotificationTemplateSerializer(read_only=True)
    created_by = UserListSerializer(read_only=True)
    
    class Meta:
        model = NotificationBatch
        fields = [
            'id', 'name', 'notification_type', 'recipient_count',
            'recipients_data', 'template', 'template_data', 'status',
            'sent_count', 'failed_count', 'scheduled_at', 'started_at',
            'completed_at', 'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'sent_count', 'failed_count', 'started_at', 'completed_at',
            'created_by', 'created_at', 'updated_at'
        ]


class NotificationBatchCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating notification batches"""
    
    class Meta:
        model = NotificationBatch
        fields = [
            'name', 'notification_type', 'recipients_data',
            'template', 'template_data', 'scheduled_at'
        ]
    
    def create(self, validated_data):
        """Create notification batch"""
        user = self.context['request'].user
        validated_data['created_by'] = user
        validated_data['recipient_count'] = len(validated_data.get('recipients_data', []))
        
        batch = NotificationBatch.objects.create(**validated_data)
        # TODO: Trigger batch processing via Celery
        return batch


class NotificationStatsSerializer(serializers.Serializer):
    """Serializer for notification statistics"""
    total_notifications = serializers.IntegerField()
    unread_count = serializers.IntegerField()
    read_count = serializers.IntegerField()
    archived_count = serializers.IntegerField()
    by_type = serializers.DictField()
    by_priority = serializers.DictField()
    recent_notifications = NotificationListSerializer(many=True)


class MarkAsReadSerializer(serializers.Serializer):
    """Serializer for marking notifications as read"""
    notification_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False
    )
    mark_all = serializers.BooleanField(default=False)


class BulkActionSerializer(serializers.Serializer):
    """Serializer for bulk notification actions"""
    notification_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=True
    )
    action = serializers.ChoiceField(
        choices=['read', 'unread', 'archive', 'unarchive', 'delete']
    )


class TaskAlertKeywordSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskAlertKeyword
        fields = ["id", "user", "keyword", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "user", "created_at", "updated_at"]

