"""
Locations App Configuration
"""
from django.apps import AppConfig


class LocationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.locations'
    verbose_name = 'Locations'
    
    def ready(self):
        """Import signals when app is ready"""
        try:
            import apps.locations.signals  # noqa
        except ImportError:
            pass
