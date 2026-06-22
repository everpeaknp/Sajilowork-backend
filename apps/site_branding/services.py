from django.contrib.sites.models import Site

from .models import SiteBranding


def get_site_branding(site_id: int | None = None) -> SiteBranding | None:
    from django.conf import settings

    site_id = site_id or getattr(settings, 'SITE_ID', 1)
    return (
        SiteBranding.objects.select_related('site')
        .filter(site_id=site_id)
        .first()
    )


def get_public_site_settings(site_id: int | None = None, request=None) -> dict:
    from django.conf import settings

    site_id = site_id or getattr(settings, 'SITE_ID', 1)
    site = Site.objects.filter(pk=site_id).first()
    branding = get_site_branding(site_id)

    favicon_url = (branding.favicon_url or None) if branding else None

    return {
        'site_name': site.name if site else 'Sajilowork',
        'site_domain': site.domain if site else '',
        'favicon_url': favicon_url,
    }
