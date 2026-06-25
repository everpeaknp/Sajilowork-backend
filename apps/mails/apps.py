from django.apps import AppConfig


class MailsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.mails'
    verbose_name = 'Email Management'
    
    def ready(self):
        """Import signals when app is ready"""
        import apps.mails.signals  # noqa
