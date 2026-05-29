from django.apps import AppConfig


class WalletsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.wallets'
    verbose_name = 'Wallets'
    
    def ready(self):
        """Import signal handlers when app is ready"""
        import apps.wallets.signals
