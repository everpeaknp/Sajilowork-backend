"""
Chat app configuration.
"""
from django.apps import AppConfig


class ChatConfig(AppConfig):
    """Configuration for chat app."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.chat'
    verbose_name = 'Chat'
    
    def ready(self):
        """Import signal handlers when app is ready."""
        import apps.chat.signals
