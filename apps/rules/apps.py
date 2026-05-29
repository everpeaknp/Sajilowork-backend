from django.apps import AppConfig


class RulesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.rules'
    verbose_name = 'Rules'

    def ready(self):
        # Ensure admin models are registered when the app loads
        from . import admin  # noqa: F401
