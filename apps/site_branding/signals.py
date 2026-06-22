from django.contrib.sites.models import Site
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import SiteBranding


@receiver(post_save, sender=Site)
def ensure_site_branding(sender, instance, **kwargs):
    SiteBranding.objects.get_or_create(site=instance)
