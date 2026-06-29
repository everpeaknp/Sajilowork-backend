from django.conf import settings
from django.contrib.sites.models import Site

from .models import SiteBranding

PLACEHOLDER_SITE_DOMAINS = frozenset(
    {'example.com', 'www.example.com', 'localhost', '127.0.0.1'},
)


PLACEHOLDER_SITE_NAMES = frozenset({
    'example.com',
    'example',
    'localhost',
    'tasknepal',
    'task nepal',
    'airtasker',
})

DEFAULT_META_DESCRIPTION = (
    'Hire skilled taskers and freelancers in Nepal. Post tasks, find jobs, '
    'book local services, and get work done securely on Sajilowork.'
)


def _default_og_image_url() -> str:
    frontend = getattr(settings, 'FRONTEND_URL', 'https://www.sajilowork.com').rstrip('/')
    if not frontend.startswith('http'):
        frontend = f'https://{frontend}'
    return f'{frontend}/opengraph-image'


def _social_urls_from_branding(branding: SiteBranding | None) -> list[str]:
    if not branding:
        return []
    urls = []
    for field in ('facebook_url', 'linkedin_url', 'instagram_url'):
        value = (getattr(branding, field, '') or '').strip()
        if value:
            urls.append(value)
    return urls


def resolve_public_site_name(raw_name: str | None) -> str:
    """Return a real site name, not Django's default example.com placeholder."""
    name = (raw_name or '').strip()
    if not name:
        return 'Sajilowork'
    lowered = name.lower()
    if lowered in PLACEHOLDER_SITE_NAMES or lowered.startswith('localhost'):
        return 'Sajilowork'
    return name


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
        frontend_host = frontend.replace('https://', '').replace('http://', '').strip('/').lower()
        if (
            frontend_host
            and frontend_host not in PLACEHOLDER_SITE_DOMAINS
            and not frontend_host.startswith('localhost')
            and not frontend_host.startswith('127.0.0.1')
        ):
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
    logo_url = (branding.logo_url or None) if branding else None
    display_name_raw = (branding.display_name or '').strip() if branding else ''
    site_name = resolve_public_site_name(site.name if site else '')
    display_name = display_name_raw or site_name
    meta_description = ((branding.meta_description or '').strip() if branding else '') or DEFAULT_META_DESCRIPTION
    og_image_url = ((branding.og_image_url or '').strip() if branding else '') or _default_og_image_url()

    return {
        'site_name': site_name,
        'display_name': display_name,
        'site_domain': resolve_public_site_domain(site.domain if site else ''),
        'logo_url': logo_url,
        'favicon_url': favicon_url,
        'meta_description': meta_description,
        'og_image_url': og_image_url,
        'twitter_handle': (branding.twitter_handle or None) if branding else None,
        'contact_email': (branding.contact_email or None) if branding else None,
        'same_as': _social_urls_from_branding(branding),
    }
