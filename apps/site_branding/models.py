from django.contrib.sites.models import Site
from django.db import models
from django.utils.translation import gettext_lazy as _


class SiteBranding(models.Model):
    """Global site branding and SEO settings."""

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
    meta_description = models.CharField(
        max_length=320,
        blank=True,
        default='',
        help_text=_('Default meta description for search engines and social sharing.'),
    )
    og_image_url = models.URLField(
        blank=True,
        default='',
        help_text=_('Default Open Graph image URL (1200×630 recommended).'),
    )
    twitter_handle = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text=_('Twitter/X handle without @ (e.g. sajilowork).'),
    )
    contact_email = models.EmailField(
        blank=True,
        default='',
        help_text=_('Public support email for Organization schema and contact pages.'),
    )
    facebook_url = models.URLField(
        blank=True,
        default='',
        help_text=_('Facebook page URL for Organization sameAs schema.'),
    )
    linkedin_url = models.URLField(
        blank=True,
        default='',
        help_text=_('LinkedIn company/profile URL for Organization sameAs schema.'),
    )
    instagram_url = models.URLField(
        blank=True,
        default='',
        help_text=_('Instagram profile URL for Organization sameAs schema.'),
    )

    class Meta:
        verbose_name = _('Site branding')
        verbose_name_plural = _('Site branding')

    def __str__(self):
        return f'Branding for {self.site.name}'

    @property
    def has_favicon(self) -> bool:
        return bool(self.favicon_url)
