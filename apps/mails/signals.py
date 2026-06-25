"""
Email Management Signals
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.cache import cache
from .models import SMTPConfiguration, EmailSetting


@receiver(post_save, sender=SMTPConfiguration)
def clear_smtp_cache(sender, instance, **kwargs):
    """
    Clear SMTP configuration cache when updated
    """
    cache.delete('active_smtp_config')


@receiver(post_save, sender=EmailSetting)
def clear_email_settings_cache(sender, instance, **kwargs):
    """
    Clear email settings cache when updated
    """
    cache.delete('email_settings')


@receiver(pre_save, sender=SMTPConfiguration)
def ensure_single_active_smtp(sender, instance, **kwargs):
    """
    Ensure only one SMTP configuration is active at a time
    """
    if instance.is_active:
        SMTPConfiguration.objects.exclude(pk=instance.pk).update(is_active=False)
