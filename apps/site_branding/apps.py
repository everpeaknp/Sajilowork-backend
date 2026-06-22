from django.apps import AppConfig


class SiteBrandingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.site_branding'
    verbose_name = 'Site branding'

    def ready(self):
        from . import signals  # noqa: F401
