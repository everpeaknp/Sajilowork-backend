"""
Notifications App URLs
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    NotificationViewSet, NotificationPreferenceViewSet,
    DeviceTokenViewSet, EmailNotificationViewSet,
    PushNotificationViewSet, NotificationTemplateViewSet,
    NotificationBatchViewSet, TaskAlertKeywordViewSet
)

app_name = 'notifications'

router = DefaultRouter()
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'preferences', NotificationPreferenceViewSet, basename='preference')
router.register(r'device-tokens', DeviceTokenViewSet, basename='device-token')
router.register(r'email-notifications', EmailNotificationViewSet, basename='email-notification')
router.register(r'push-notifications', PushNotificationViewSet, basename='push-notification')
router.register(r'templates', NotificationTemplateViewSet, basename='template')
router.register(r'batches', NotificationBatchViewSet, basename='batch')
router.register(r'task-alert-keywords', TaskAlertKeywordViewSet, basename='task-alert-keyword')

urlpatterns = [
    path('', include(router.urls)),
]
