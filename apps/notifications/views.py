"""
Notifications App Views
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from django.db.models import Q, Count
from django.utils import timezone
from .models import (
    Notification, NotificationPreference, EmailNotification,
    PushNotification, DeviceToken, NotificationTemplate, NotificationBatch,
    TaskAlertKeyword
)
from .serializers import (
    NotificationSerializer, NotificationListSerializer, NotificationCreateSerializer,
    NotificationPreferenceSerializer, NotificationPreferenceUpdateSerializer,
    EmailNotificationSerializer, PushNotificationSerializer,
    DeviceTokenSerializer, DeviceTokenCreateSerializer,
    NotificationTemplateSerializer, NotificationBatchSerializer,
    NotificationBatchCreateSerializer, NotificationStatsSerializer,
    MarkAsReadSerializer, BulkActionSerializer,
    TaskAlertKeywordSerializer
)
from .permissions import IsNotificationRecipient, IsNotificationOwner


class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing notifications
    """
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return NotificationListSerializer
        elif self.action == 'create':
            return NotificationCreateSerializer
        return NotificationSerializer
    
    def get_queryset(self):
        """Get notifications for current user"""
        user = self.request.user
        queryset = Notification.objects.filter(recipient=user)
        
        # Filter by read status
        is_read = self.request.query_params.get('is_read')
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == 'true')
        
        # Filter by archived status
        is_archived = self.request.query_params.get('is_archived')
        if is_archived is not None:
            queryset = queryset.filter(is_archived=is_archived.lower() == 'true')
        else:
            # By default, exclude archived
            queryset = queryset.filter(is_archived=False)
        
        # Filter by notification type
        notification_type = self.request.query_params.get('type')
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        
        # Filter by priority
        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        return queryset.select_related('sender')
    
    def perform_create(self, serializer):
        """Create notification"""
        serializer.save()
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark notification as read"""
        notification = self.get_object()
        notification.mark_as_read()
        return Response({'status': 'notification marked as read'})
    
    @action(detail=True, methods=['post'])
    def mark_unread(self, request, pk=None):
        """Mark notification as unread"""
        notification = self.get_object()
        notification.is_read = False
        notification.read_at = None
        notification.save(update_fields=['is_read', 'read_at'])
        return Response({'status': 'notification marked as unread'})
    
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archive notification"""
        notification = self.get_object()
        notification.archive()
        return Response({'status': 'notification archived'})
    
    @action(detail=True, methods=['post'])
    def unarchive(self, request, pk=None):
        """Unarchive notification"""
        notification = self.get_object()
        notification.is_archived = False
        notification.archived_at = None
        notification.save(update_fields=['is_archived', 'archived_at'])
        return Response({'status': 'notification unarchived'})
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read"""
        serializer = MarkAsReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        
        if serializer.validated_data.get('mark_all'):
            # Mark all unread notifications as read
            updated = Notification.objects.filter(
                recipient=user,
                is_read=False
            ).update(
                is_read=True,
                read_at=timezone.now()
            )
        else:
            # Mark specific notifications as read
            notification_ids = serializer.validated_data.get('notification_ids', [])
            updated = Notification.objects.filter(
                recipient=user,
                id__in=notification_ids,
                is_read=False
            ).update(
                is_read=True,
                read_at=timezone.now()
            )
        
        return Response({
            'status': 'notifications marked as read',
            'count': updated
        })
    
    @action(detail=False, methods=['post'])
    def bulk_action(self, request):
        """Perform bulk actions on notifications"""
        serializer = BulkActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        notification_ids = serializer.validated_data['notification_ids']
        action_type = serializer.validated_data['action']
        
        notifications = Notification.objects.filter(
            recipient=user,
            id__in=notification_ids
        )
        
        if action_type == 'read':
            updated = notifications.update(is_read=True, read_at=timezone.now())
        elif action_type == 'unread':
            updated = notifications.update(is_read=False, read_at=None)
        elif action_type == 'archive':
            updated = notifications.update(is_archived=True, archived_at=timezone.now())
        elif action_type == 'unarchive':
            updated = notifications.update(is_archived=False, archived_at=None)
        elif action_type == 'delete':
            updated = notifications.count()
            notifications.delete()
        else:
            return Response(
                {'error': 'Invalid action'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({
            'status': f'bulk {action_type} completed',
            'count': updated
        })
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get unread notification count"""
        user = request.user
        count = Notification.objects.filter(
            recipient=user,
            is_read=False,
            is_archived=False
        ).count()
        
        return Response({'count': count})
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get notification statistics"""
        user = request.user
        
        notifications = Notification.objects.filter(recipient=user)
        
        # Count by status
        total = notifications.count()
        unread = notifications.filter(is_read=False, is_archived=False).count()
        read = notifications.filter(is_read=True, is_archived=False).count()
        archived = notifications.filter(is_archived=True).count()
        
        # Count by type
        by_type = dict(
            notifications.values('notification_type')
            .annotate(count=Count('id'))
            .values_list('notification_type', 'count')
        )
        
        # Count by priority
        by_priority = dict(
            notifications.values('priority')
            .annotate(count=Count('id'))
            .values_list('priority', 'count')
        )
        
        # Recent notifications
        recent = notifications.filter(is_archived=False)[:10]
        
        stats_data = {
            'total_notifications': total,
            'unread_count': unread,
            'read_count': read,
            'archived_count': archived,
            'by_type': by_type,
            'by_priority': by_priority,
            'recent_notifications': recent
        }
        
        serializer = NotificationStatsSerializer(stats_data)
        return Response(serializer.data)


class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing notification preferences
    """
    permission_classes = [IsAuthenticated, IsNotificationOwner]
    serializer_class = NotificationPreferenceSerializer
    
    def get_queryset(self):
        """Get preferences for current user"""
        return NotificationPreference.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return NotificationPreferenceUpdateSerializer
        return NotificationPreferenceSerializer
    
    def perform_create(self, serializer):
        """Create preference for current user"""
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def defaults(self, request):
        """Get default notification preferences"""
        # Return default preferences for all notification types
        notification_types = dict(Notification.NOTIFICATION_TYPES)
        
        defaults = []
        for type_key, type_label in notification_types.items():
            defaults.append({
                'notification_type': type_key,
                'label': type_label,
                'in_app_enabled': True,
                'email_enabled': True,
                'push_enabled': True,
                'sms_enabled': False,
                'instant': True,
                'daily_digest': False,
                'weekly_digest': False
            })
        
        return Response(defaults)
    
    @action(detail=False, methods=['post'])
    def reset_to_defaults(self, request):
        """Reset all preferences to defaults"""
        user = request.user
        
        # Delete all existing preferences
        NotificationPreference.objects.filter(user=user).delete()
        
        # Create default preferences
        notification_types = dict(Notification.NOTIFICATION_TYPES)
        preferences = []
        
        for type_key in notification_types.keys():
            preferences.append(
                NotificationPreference(
                    user=user,
                    notification_type=type_key,
                    in_app_enabled=True,
                    email_enabled=True,
                    push_enabled=True,
                    sms_enabled=False,
                    instant=True
                )
            )
        
        NotificationPreference.objects.bulk_create(preferences)
        
        return Response({'status': 'preferences reset to defaults'})


class TaskAlertKeywordViewSet(viewsets.ModelViewSet):
    """
    Keyword alerts for matching tasks.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = TaskAlertKeywordSerializer

    def get_queryset(self):
        return TaskAlertKeyword.objects.filter(user=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        keyword = (serializer.validated_data.get("keyword") or "").strip()
        if not keyword:
            raise ValidationError({"keyword": "Keyword is required"})
        if len(keyword) > 64:
            raise ValidationError({"keyword": "Keyword too long"})

        serializer.save(user=self.request.user, keyword=keyword)


class DeviceTokenViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing device tokens
    """
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return DeviceTokenCreateSerializer
        return DeviceTokenSerializer
    
    def get_queryset(self):
        """Get device tokens for current user"""
        return DeviceToken.objects.filter(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate device token"""
        device_token = self.get_object()
        device_token.is_active = False
        device_token.save(update_fields=['is_active'])
        return Response({'status': 'device token deactivated'})
    
    @action(detail=False, methods=['post'])
    def deactivate_all(self, request):
        """Deactivate all device tokens for current user"""
        user = request.user
        updated = DeviceToken.objects.filter(
            user=user,
            is_active=True
        ).update(is_active=False)
        
        return Response({
            'status': 'all device tokens deactivated',
            'count': updated
        })


class EmailNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing email notifications (read-only)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = EmailNotificationSerializer
    
    def get_queryset(self):
        """Get email notifications for current user"""
        user = self.request.user
        return EmailNotification.objects.filter(
            notification__recipient=user
        ).select_related('notification')


class PushNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing push notifications (read-only)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = PushNotificationSerializer
    
    def get_queryset(self):
        """Get push notifications for current user"""
        user = self.request.user
        return PushNotification.objects.filter(
            notification__recipient=user
        ).select_related('notification')


class NotificationTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing notification templates (admin only)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationTemplateSerializer
    queryset = NotificationTemplate.objects.all()
    
    def get_queryset(self):
        """Filter templates"""
        queryset = super().get_queryset()
        
        # Filter by notification type
        notification_type = self.request.query_params.get('type')
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        
        # Filter by channel
        channel = self.request.query_params.get('channel')
        if channel:
            queryset = queryset.filter(channel=channel)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset


class NotificationBatchViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing notification batches (admin only)
    """
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return NotificationBatchCreateSerializer
        return NotificationBatchSerializer
    
    def get_queryset(self):
        """Get notification batches"""
        user = self.request.user
        
        # Admin can see all batches, others see only their own
        if user.is_staff:
            return NotificationBatch.objects.all()
        return NotificationBatch.objects.filter(created_by=user)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a pending batch"""
        batch = self.get_object()
        
        if batch.status not in ['pending', 'processing']:
            return Response(
                {'error': 'Can only cancel pending or processing batches'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        batch.status = 'cancelled'
        batch.save(update_fields=['status'])
        
        return Response({'status': 'batch cancelled'})
    
    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """Retry a failed batch"""
        batch = self.get_object()
        
        if batch.status != 'failed':
            return Response(
                {'error': 'Can only retry failed batches'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        batch.status = 'pending'
        batch.sent_count = 0
        batch.failed_count = 0
        batch.save(update_fields=['status', 'sent_count', 'failed_count'])
        
        # TODO: Trigger batch processing via Celery
        
        return Response({'status': 'batch queued for retry'})
