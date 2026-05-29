"""
Reviews app configuration.
"""
from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    """Configuration for Reviews app."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.reviews'
    verbose_name = 'Reviews'
    
    def ready(self):
        """Import signal handlers when app is ready."""
        import apps.reviews.signals
