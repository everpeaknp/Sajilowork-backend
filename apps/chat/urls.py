"""
URL configuration for chat app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ConversationViewSet, MessageViewSet, TypingIndicatorViewSet,
    ConversationMuteViewSet, MessageReportViewSet
)

app_name = 'chat'

router = DefaultRouter()
router.register(r'conversations', ConversationViewSet, basename='conversation')
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'typing-indicators', TypingIndicatorViewSet, basename='typing-indicator')
router.register(r'conversation-mutes', ConversationMuteViewSet, basename='conversation-mute')
router.register(r'message-reports', MessageReportViewSet, basename='message-report')

urlpatterns = [
    path('', include(router.urls)),
]
