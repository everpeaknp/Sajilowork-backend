from django.conf import settings
from django.contrib.sites.models import Site

from .models import SiteBranding

PLACEHOLDER_SITE_DOMAINS = frozenset(
    {'example.com', 'www.example.com', 'localhost', '127.0.0.1'},
)


def resolve_public_site_domain(raw_domain: str | None) -> str:
    """Return a real public hostname, not Django's default example.com placeholder."""
    domain = (raw_domain or '').strip().lower()
    domain = domain.replace('https://', '').replace('http://', '').strip('/')

    if (
        not domain
        or domain in PLACEHOLDER_SITE_DOMAINS
        or domain.startswith('localhost')
        or domain.startswith('127.0.0.1')
    ):
        frontend = getattr(settings, 'FRONTEND_URL', '').rstrip('/')
        frontend_host = frontend.replace('https://', '').replace('http://', '').strip('/')
        if frontend_host and frontend_host not in PLACEHOLDER_SITE_DOMAINS:
            return frontend_host
        return 'www.sajilowork.com'

    return domain


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
        'site_domain': resolve_public_site_domain(site.domain if site else ''),
        'favicon_url': favicon_url,
        'meta_description': (branding.meta_description or None) if branding else None,
        'og_image_url': (branding.og_image_url or None) if branding else None,
        'twitter_handle': (branding.twitter_handle or None) if branding else None,
        'contact_email': (branding.contact_email or None) if branding else None,
    }
