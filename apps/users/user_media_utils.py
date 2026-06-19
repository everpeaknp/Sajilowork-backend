"""Resolve and store user profile/cover media (Cloudinary URL or local file path)."""
from django.core.files.storage import default_storage

from apps.uploads.cloudinary_utils import is_cloudinary_url


def resolve_user_media_url(request, stored_value: str | None) -> str | None:
    if not stored_value:
        return None

    value = str(stored_value).strip()
    if not value:
        return None

    if value.startswith('http://') or value.startswith('https://'):
        return value

    media_url = default_storage.url(value)
    if media_url.startswith('http://') or media_url.startswith('https://'):
        return media_url
    if request is not None:
        return request.build_absolute_uri(media_url)
    return media_url


def clear_stored_user_media(stored_value: str | None) -> None:
    """Remove a locally stored file. Cloudinary assets are left on the CDN."""
    if not stored_value:
        return

    value = str(stored_value).strip()
    if not value or is_cloudinary_url(value):
        return
    if value.startswith('http://') or value.startswith('https://'):
        return

    try:
        if default_storage.exists(value):
            default_storage.delete(value)
    except Exception:
        pass
