"""
Uploads App Configuration
"""
from django.apps import AppConfig


class UploadsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.uploads'
    verbose_name = 'Uploads'
    
    def ready(self):
        """Import signals when app is ready"""
        import apps.uploads.signals
