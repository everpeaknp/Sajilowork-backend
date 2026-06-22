from django.contrib.sites.models import Site
from django.db import models
from django.utils.translation import gettext_lazy as _


class SiteBranding(models.Model):
    """Favicon and extra branding for a django.contrib.sites Site."""

    site = models.OneToOneField(
        Site,
        on_delete=models.CASCADE,
        related_name='branding',
    )
    favicon_url = models.URLField(
        blank=True,
        default='',
        help_text=_('Cloudinary URL for the site favicon (PNG or ICO, 48×48 recommended).'),
    )

    class Meta:
        verbose_name = _('Site favicon')
        verbose_name_plural = _('Site favicons')

    def __str__(self):
        return f'Branding for {self.site.name}'

    @property
    def has_favicon(self) -> bool:
        return bool(self.favicon_url)
