"""Employer profile helpers: defaults, media limits, and user lookup."""
import os
import re
import uuid

from django.core.files.storage import default_storage
from django.db.models import Q

from .models import EmployerGalleryImage, EmployerProfile, User

MAX_EMPLOYER_GALLERY_ITEMS = 10
MAX_EMPLOYER_LOGO_BYTES = 1024 * 1024
MAX_EMPLOYER_GALLERY_BYTES = 1024 * 1024
ALLOWED_EMPLOYER_IMAGE_CONTENT_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
}


def build_default_employer_profile(user: User) -> EmployerProfile:
    company_name = user.get_full_name() or (user.username or '').strip()
    initials = ''.join(part[0] for part in company_name.split()[:2]).upper() or 'CO'
    return EmployerProfile(
        user=user,
        account_type='individual',
        company_name=company_name,
        industry='',
        team_size='',
        website='',
        cost_range='',
        contact_email=user.email or '',
        contact_phone=user.phone or '',
        logo_color='serif-m',
        logo_text=initials,
        is_public=True,
    )


def get_or_create_employer_profile(user: User) -> EmployerProfile:
    profile = EmployerProfile.objects.filter(user=user).first()
    if profile:
        return profile
    defaults = build_default_employer_profile(user)
    return EmployerProfile.objects.create(
        user=user,
        account_type=defaults.account_type,
        company_name=defaults.company_name,
        industry=defaults.industry,
        team_size=defaults.team_size,
        website=defaults.website,
        cost_range=defaults.cost_range,
        contact_email=defaults.contact_email,
        contact_phone=defaults.contact_phone,
        logo_color=defaults.logo_color,
        logo_text=defaults.logo_text,
        is_public=defaults.is_public,
    )


def _employer_eligible_users():
    return (
        User.objects.filter(
            is_active=True,
            account_suspended=False,
        )
        .filter(Q(role='customer') | Q(employer_profile__isnull=False))
        .select_related('employer_profile')
        .prefetch_related('employer_profile__gallery_images')
    )


def get_employer_user_by_slug(slug: str) -> User | None:
    """Resolve employer account from public profile URL segment (username or alias)."""
    normalized = (slug or '').strip().lower()
    if not normalized:
        return None

    queryset = _employer_eligible_users()

    user = queryset.filter(username__iexact=normalized).first()
    if user:
        return user

    try:
        user = queryset.filter(id=uuid.UUID(normalized)).first()
        if user:
            return user
    except ValueError:
        pass

    # Email local-part alias: /employers/bishal may match bishal@baniya.com when username differs.
    email_local_pattern = rf'^{re.escape(normalized)}@'
    return queryset.filter(email__iregex=email_local_pattern).first()


def save_employer_logo_upload(user: User, uploaded_file) -> str:
    ext = os.path.splitext(uploaded_file.name)[1].lower() or '.jpg'
    filename = f'{uuid.uuid4().hex}{ext}'
    relative_path = f'employer_logos/{user.id}/{filename}'
    return default_storage.save(relative_path, uploaded_file)


def save_employer_gallery_upload(user: User, uploaded_file) -> str:
    ext = os.path.splitext(uploaded_file.name)[1].lower() or '.jpg'
    filename = f'{uuid.uuid4().hex}{ext}'
    relative_path = f'employer_gallery/{user.id}/{filename}'
    return default_storage.save(relative_path, uploaded_file)


def build_employer_media_url(request, storage_path: str) -> str:
    media_url = default_storage.url(storage_path)
    if media_url.startswith('http://') or media_url.startswith('https://'):
        return media_url
    return request.build_absolute_uri(media_url)


def resolve_employer_image_url(request, image_field) -> str | None:
    if not image_field:
        return None
    try:
        url = image_field.url
    except (ValueError, AttributeError):
        return None
    if url.startswith('http://') or url.startswith('https://'):
        return url
    if request:
        return request.build_absolute_uri(url)
    return url


def count_open_employer_listings(user: User, listing_kind: str) -> int:
    from apps.tasks.listing import filter_queryset_by_listing_kind
    from apps.tasks.models import Task

    queryset = Task.objects.filter(owner=user, is_public=True, status='open')
    return filter_queryset_by_listing_kind(queryset, listing_kind).count()
