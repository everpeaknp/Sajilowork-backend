"""Badge sync and request helpers for tasker verification badges."""

from __future__ import annotations

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .badge_catalog import (
    AUTO_BADGE_TYPES,
    BADGE_CATALOG,
    DOCUMENT_REQUIRED_BADGE_TYPES,
    MAX_CUSTOM_LICENCE_BADGES_PER_USER,
    REQUESTABLE_BADGE_TYPES,
)
from .models import UserBadge, UserDocument

ALLOWED_BADGE_DOCUMENT_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
    'application/pdf',
}
MAX_BADGE_DOCUMENT_BYTES = 10 * 1024 * 1024


def _catalog_defaults(badge_type: str) -> tuple[str, str]:
    name, description = BADGE_CATALOG.get(
        badge_type,
        (badge_type.replace('_', ' ').title(), ''),
    )
    return name, description


def _upsert_badge(user, badge_type: str, *, is_verified: bool) -> UserBadge:
    name, description = _catalog_defaults(badge_type)
    badge, _created = UserBadge.objects.update_or_create(
        user=user,
        badge_type=badge_type,
        name=name,
        defaults={
            'description': description,
            'is_verified': is_verified,
            'verified_at': timezone.now() if is_verified else None,
        },
    )
    return badge


def sync_auto_badges(user) -> list[UserBadge]:
    """Create or update badges derived from the user profile."""
    synced: list[UserBadge] = []

    if user.phone_verified:
        synced.append(_upsert_badge(user, 'mobile_verified', is_verified=True))
    else:
        UserBadge.objects.filter(user=user, badge_type='mobile_verified').update(
            is_verified=False,
            verified_at=None,
        )

    if user.has_payment_method:
        synced.append(_upsert_badge(user, 'payment_verified', is_verified=True))
    else:
        UserBadge.objects.filter(user=user, badge_type='payment_verified').update(
            is_verified=False,
            verified_at=None,
        )

    if user.identity_verified:
        synced.append(_upsert_badge(user, 'identity_verified', is_verified=True))

    return synced


def validate_badge_document(uploaded_file) -> None:
    if uploaded_file is None:
        raise ValidationError({'verification_document': 'A document file is required.'})
    if uploaded_file.size > MAX_BADGE_DOCUMENT_BYTES:
        raise ValidationError(
            {'verification_document': 'File size exceeds 10MB limit.'}
        )
    content_type = getattr(uploaded_file, 'content_type', '') or ''
    if content_type not in ALLOWED_BADGE_DOCUMENT_TYPES:
        raise ValidationError(
            {
                'verification_document': 'Only JPG, PNG, WebP, and PDF files are allowed.',
            }
        )


def _document_link_key(badge: UserBadge) -> str:
    """Stable key stored in UserDocument.document_number for badge linkage."""
    if badge.badge_type == 'custom_licence':
        return f'badge:{badge.id}'
    return badge.document_number or ''


def _sync_user_document_for_badge(user, badge: UserBadge, *, document_url: str) -> None:
    if badge.badge_type not in DOCUMENT_REQUIRED_BADGE_TYPES:
        return

    if badge.badge_type == 'custom_licence':
        link_key = _document_link_key(badge)
        licence_ref = badge.document_number or ''
        stored_number = f'{link_key}|{licence_ref}' if licence_ref else link_key
        existing = UserDocument.objects.filter(
            user=user,
            document_type='custom_licence',
            document_number__startswith=link_key,
        ).first()
        if existing:
            existing.document_url = document_url
            existing.document_number = stored_number
            existing.status = 'pending'
            existing.rejection_reason = ''
            existing.verified_at = None
            existing.verified_by = None
            existing.save()
            return
        UserDocument.objects.create(
            user=user,
            document_type='custom_licence',
            document_url=document_url,
            document_number=stored_number,
            status='pending',
        )
        return

    UserDocument.objects.update_or_create(
        user=user,
        document_type=badge.badge_type,
        defaults={
            'document_url': document_url,
            'document_number': badge.document_number or '',
            'status': 'pending',
            'rejection_reason': '',
            'verified_at': None,
            'verified_by': None,
        },
    )


def request_badge(
    user,
    badge_type: str,
    *,
    uploaded_file=None,
    document_number: str = '',
    custom_name: str = '',
    custom_description: str = '',
) -> tuple[UserBadge, bool]:
    """Request a badge that requires admin review."""
    if badge_type in AUTO_BADGE_TYPES:
        raise ValidationError(
            {'badge_type': 'This badge is granted automatically from your profile.'}
        )

    if badge_type not in REQUESTABLE_BADGE_TYPES:
        raise ValidationError({'badge_type': 'This badge type cannot be requested.'})

    if badge_type in DOCUMENT_REQUIRED_BADGE_TYPES:
        validate_badge_document(uploaded_file)

    if badge_type == 'custom_licence':
        name = (custom_name or '').strip()
        if len(name) < 2:
            raise ValidationError({'name': 'Enter a name for your licence or certification.'})
        if len(name) > 100:
            raise ValidationError({'name': 'Name must be 100 characters or fewer.'})

        custom_count = UserBadge.objects.filter(
            user=user,
            badge_type='custom_licence',
        ).count()
        if custom_count >= MAX_CUSTOM_LICENCE_BADGES_PER_USER:
            raise ValidationError(
                {
                    'badge_type': (
                        f'You can add up to {MAX_CUSTOM_LICENCE_BADGES_PER_USER} '
                        'custom licence badges.'
                    ),
                }
            )

        if UserBadge.objects.filter(
            user=user,
            badge_type='custom_licence',
            name__iexact=name,
            is_verified=True,
        ).exists():
            raise ValidationError({'name': 'You already have this custom badge active.'})

        description = (custom_description or '').strip()
        badge, created = UserBadge.objects.get_or_create(
            user=user,
            badge_type='custom_licence',
            name=name,
            defaults={
                'description': description,
                'is_verified': False,
            },
        )
        badge.description = description
        badge.document_number = (document_number or '').strip()
        if uploaded_file is not None:
            badge.verification_document = uploaded_file
        badge.is_verified = False
        badge.verified_at = None
        badge.save()
        return badge, created

    name, description = _catalog_defaults(badge_type)
    if UserBadge.objects.filter(
        user=user,
        badge_type=badge_type,
        name=name,
        is_verified=True,
    ).exists():
        raise ValidationError({'badge_type': 'You already have this badge active.'})

    badge, created = UserBadge.objects.get_or_create(
        user=user,
        badge_type=badge_type,
        name=name,
        defaults={
            'description': description,
            'is_verified': False,
        },
    )
    badge.description = description
    badge.document_number = (document_number or '').strip()

    if uploaded_file is not None:
        badge.verification_document = uploaded_file

    badge.is_verified = False
    badge.verified_at = None
    badge.save()

    return badge, created


def request_or_sync_badge(
    user,
    badge_type: str,
    *,
    uploaded_file=None,
    document_number: str = '',
    custom_name: str = '',
    custom_description: str = '',
) -> UserBadge:
    """Handle dashboard Add for payment or requestable badges."""
    if badge_type == 'payment_verified':
        if not user.has_payment_method:
            raise ValidationError(
                {'badge_type': 'Link a payment method in Payment Methods first.'}
            )
        sync_auto_badges(user)
        badge = UserBadge.objects.filter(user=user, badge_type='payment_verified').first()
        if badge is None:
            raise ValidationError({'badge_type': 'Unable to verify payment method.'})
        return badge

    badge, _created = request_badge(
        user,
        badge_type,
        uploaded_file=uploaded_file,
        document_number=document_number,
        custom_name=custom_name,
        custom_description=custom_description,
    )
    return badge
