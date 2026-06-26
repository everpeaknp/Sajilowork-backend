"""
DRF Serializers for Email Management System
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    EmailTemplate,
    EmailSetting,
    SMTPConfiguration,
    NotificationRule,
    EmailLog,
    ContactSubmission
)

User = get_user_model()


class EmailTemplateListSerializer(serializers.ModelSerializer):
    """Serializer for email template list view (minimal fields)"""
    
    created_by_name = serializers.SerializerMethodField()
    channel_count = serializers.SerializerMethodField()
    
    class Meta:
        model = EmailTemplate
        fields = [
            'id', 'name', 'slug', 'description', 'template_type',
            'is_active', 'language_code', 'template_group',
            'created_at', 'updated_at', 'created_by_name', 'channel_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_created_by_name(self, obj):
        """Get creator name"""
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return None
    
    def get_channel_count(self, obj):
        """Count enabled channels"""
        count = 0
        if obj.send_email:
            count += 1
        if obj.send_in_app_notification:
            count += 1
        if obj.send_push_notification:
            count += 1
        return count


class EmailTemplateSerializer(serializers.ModelSerializer):
    """Full serializer for email template CRUD operations"""
    
    created_by_name = serializers.SerializerMethodField()
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = EmailTemplate
        fields = [
            'id', 'name', 'slug', 'description', 'template_type',
            'subject', 'html_content', 'text_content',
            'send_email', 'send_in_app_notification', 'send_push_notification',
            'is_active', 'language_code', 'template_group',
            'created_at', 'updated_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']
    
    def get_created_by_name(self, obj):
        """Get creator name"""
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return None
    
    def validate_slug(self, value):
        """Validate slug uniqueness (except for current instance)"""
        queryset = EmailTemplate.objects.filter(slug=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Template with this slug already exists.")
        return value
    
    def validate_html_content(self, value):
        """Validate HTML content is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("HTML content cannot be empty.")
        return value
    
    def validate(self, data):
        """Validate at least one channel is enabled"""
        send_email = data.get('send_email', getattr(self.instance, 'send_email', True))
        send_in_app = data.get('send_in_app_notification', getattr(self.instance, 'send_in_app_notification', False))
        send_push = data.get('send_push_notification', getattr(self.instance, 'send_push_notification', False))
        
        if not any([send_email, send_in_app, send_push]):
            raise serializers.ValidationError(
                "At least one notification channel must be enabled."
            )
        
        return data


class NotificationRuleSerializer(serializers.ModelSerializer):
    """Full serializer for notification rule management"""
    
    email_template_detail = EmailTemplateListSerializer(source='email_template', read_only=True)
    
    class Meta:
        model = NotificationRule
        fields = [
            'id', 'event_name', 'event_category', 'display_name', 'description',
            'email_enabled', 'push_enabled', 'inapp_enabled', 'sms_enabled',
            'user_notification', 'admin_notification',
            'email_template', 'email_template_detail',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'event_name', 'event_category', 'display_name', 'description',
            'created_at', 'updated_at'
        ]
    
    def validate_email_template(self, value):
        """Validate template is active if email is enabled"""
        if value and not value.is_active:
            raise serializers.ValidationError(
                "Cannot assign an inactive template."
            )
        return value


class EmailLogListSerializer(serializers.ModelSerializer):
    """Serializer for email log list view (without full content)"""
    
    recipient_name = serializers.SerializerMethodField()
    template_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = EmailLog
        fields = [
            'id', 'recipient_email', 'recipient_name', 'subject',
            'status', 'status_display',
            'template_used', 'template_name',
            'sent_at', 'delivered_at', 'opened_at', 'clicked_at',
            'failed_at', 'bounced_at',
            'retry_count', 'error_message',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_recipient_name(self, obj):
        """Get recipient name"""
        if obj.recipient_user:
            return obj.recipient_user.get_full_name() or obj.recipient_user.email
        return None
    
    def get_template_name(self, obj):
        """Get template name"""
        if obj.template_used:
            return obj.template_used.name
        return None


class EmailLogDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for email log (includes full content)"""
    
    recipient_name = serializers.SerializerMethodField()
    template_detail = EmailTemplateListSerializer(source='template_used', read_only=True)
    smtp_config_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = EmailLog
        fields = [
            'id', 'recipient_email', 'recipient_name', 'recipient_user',
            'subject', 'html_content', 'text_content',
            'status', 'status_display',
            'template_used', 'template_detail',
            'smtp_config_used', 'smtp_config_name',
            'sent_at', 'delivered_at', 'opened_at', 'clicked_at',
            'failed_at', 'bounced_at',
            'error_message', 'retry_count',
            'external_id', 'metadata',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields  # All fields read-only for logs
    
    def get_recipient_name(self, obj):
        """Get recipient name"""
        if obj.recipient_user:
            return obj.recipient_user.get_full_name() or obj.recipient_user.email
        return None
    
    def get_smtp_config_name(self, obj):
        """Get SMTP config name"""
        if obj.smtp_config_used:
            return obj.smtp_config_used.name
        return None


class EmailAnalyticsSummarySerializer(serializers.Serializer):
    """Serializer for email analytics summary"""
    
    total_sent = serializers.IntegerField()
    delivered = serializers.IntegerField()
    opened = serializers.IntegerField()
    clicked = serializers.IntegerField()
    failed = serializers.IntegerField()
    bounced = serializers.IntegerField()
    
    open_rate = serializers.FloatField()
    click_rate = serializers.FloatField()
    bounce_rate = serializers.FloatField()
    delivery_rate = serializers.FloatField()


class EmailDailyStatsSerializer(serializers.Serializer):
    """Serializer for daily email statistics"""
    
    date = serializers.DateField()
    sent = serializers.IntegerField()
    delivered = serializers.IntegerField()
    opened = serializers.IntegerField()
    clicked = serializers.IntegerField()
    failed = serializers.IntegerField()


class TemplatePerformanceSerializer(serializers.Serializer):
    """Serializer for template performance metrics"""
    
    template_id = serializers.UUIDField()
    template_name = serializers.CharField()
    sent = serializers.IntegerField()
    delivered = serializers.IntegerField()
    opened = serializers.IntegerField()
    clicked = serializers.IntegerField()
    
    open_rate = serializers.FloatField()
    click_rate = serializers.FloatField()
    delivery_rate = serializers.FloatField()


class EmailAnalyticsDashboardSerializer(serializers.Serializer):
    """Serializer for complete analytics dashboard"""
    
    summary = EmailAnalyticsSummarySerializer()
    daily_stats = EmailDailyStatsSerializer(many=True)
    template_performance = TemplatePerformanceSerializer(many=True)
    category_breakdown = serializers.DictField()


class EmailPreviewSerializer(serializers.Serializer):
    """Serializer for email preview with context"""
    
    context = serializers.DictField(required=True)
    
    def validate_context(self, value):
        """Validate context is a dictionary"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Context must be a dictionary.")
        return value


class TestEmailSerializer(serializers.Serializer):
    """Serializer for sending test emails"""
    
    template_id = serializers.UUIDField(required=True)
    recipient_email = serializers.EmailField(required=True)
    context = serializers.DictField(required=False, default=dict)
    
    def validate_template_id(self, value):
        """Validate template exists and is active"""
        try:
            template = EmailTemplate.objects.get(id=value)
            if not template.is_active:
                raise serializers.ValidationError("Template is not active.")
            return value
        except EmailTemplate.DoesNotExist:
            raise serializers.ValidationError("Template not found.")


class SMTPTestSerializer(serializers.Serializer):
    """Serializer for SMTP connection testing"""
    
    test_email = serializers.EmailField(required=True)


class BulkRuleUpdateSerializer(serializers.Serializer):
    """Serializer for bulk notification rule updates"""
    
    category = serializers.CharField(required=False, allow_blank=True)
    email_enabled = serializers.BooleanField(required=False)
    push_enabled = serializers.BooleanField(required=False)
    inapp_enabled = serializers.BooleanField(required=False)
    sms_enabled = serializers.BooleanField(required=False)
    
    def validate(self, data):
        """Validate at least one field to update is provided"""
        update_fields = ['email_enabled', 'push_enabled', 'inapp_enabled', 'sms_enabled']
        if not any(field in data for field in update_fields):
            raise serializers.ValidationError(
                "At least one channel field must be provided."
            )
        return data



class ContactSubmissionSerializer(serializers.ModelSerializer):
    """Serializer for contact form submissions"""
    
    class Meta:
        model = ContactSubmission
        fields = ['id', 'name', 'email', 'message', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def validate_message(self, value):
        """Validate message is not empty and has minimum length"""
        if not value or len(value.strip()) < 10:
            raise serializers.ValidationError("Message must be at least 10 characters long.")
        return value
    
    def validate_name(self, value):
        """Validate name is not empty"""
        if not value or len(value.strip()) < 2:
            raise serializers.ValidationError("Name must be at least 2 characters long.")
        return value


# Stub serializers for incomplete mails app (to be implemented later)
class EmailSettingSerializer(serializers.ModelSerializer):
    """Stub serializer for EmailSetting"""
    class Meta:
        model = EmailSetting
        fields = '__all__'


class SMTPConfigurationSerializer(serializers.ModelSerializer):
    """Stub serializer for SMTPConfiguration"""
    class Meta:
        model = SMTPConfiguration
        fields = '__all__'


class NotificationRuleListSerializer(serializers.ModelSerializer):
    """Stub serializer for NotificationRule list"""
    class Meta:
        model = NotificationRule
        fields = '__all__'
