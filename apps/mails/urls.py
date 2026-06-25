"""
URL Configuration for Email Management System
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    EmailTemplateViewSet,
    SMTPConfigurationView,
    SMTPTestConnectionView,
    SMTPSendTestView,
    EmailSettingView,
    NotificationRuleViewSet,
    EmailLogViewSet,
    EmailAnalyticsDashboardView,
)

app_name = 'mails'

# Router for viewsets
router = DefaultRouter()

# Register viewsets
router.register(r'templates', EmailTemplateViewSet, basename='template')
router.register(r'rules', NotificationRuleViewSet, basename='rule')
router.register(r'logs', EmailLogViewSet, basename='log')

urlpatterns = [
    # ViewSet routes (includes standard CRUD + custom actions)
    path('', include(router.urls)),
    
    # SMTP Configuration endpoints (superuser only)
    path('smtp/', SMTPConfigurationView.as_view(), name='smtp-config'),
    path('smtp/test-connection/', SMTPTestConnectionView.as_view(), name='smtp-test-connection'),
    path('smtp/send-test/', SMTPSendTestView.as_view(), name='smtp-send-test'),
    
    # Email Settings endpoint (admin only)
    path('settings/', EmailSettingView.as_view(), name='email-settings'),
    
    # Analytics dashboard (admin only)
    path('analytics/dashboard/', EmailAnalyticsDashboardView.as_view(), name='analytics-dashboard'),
]
