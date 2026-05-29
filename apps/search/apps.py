"""
Search App Configuration
"""
from django.apps import AppConfig


class SearchConfig(AppConfig):
    """Configuration for Search app"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.search'
    verbose_name = 'Search'
    
    def ready(self):
        """Import signals when app is ready"""
        try:
            import apps.search.signals  # noqa
        except ImportError:
            pass
