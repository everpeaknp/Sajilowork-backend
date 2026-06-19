"""
Shared Cloudinary helpers.
"""
from django.conf import settings

ALLOWED_IMAGE_TYPES = {
    'image/jpeg',
    'image/png',
    'image/gif',
    'image/webp',
}
MAX_IMAGE_BYTES = 10 * 1024 * 1024


def cloudinary_enabled() -> bool:
    storage = getattr(settings, 'CLOUDINARY_STORAGE', {})
    cloud_name = (storage.get('CLOUD_NAME') or '').strip()
    api_key = (storage.get('API_KEY') or '').strip()
    api_secret = (storage.get('API_SECRET') or '').strip()
    return bool(cloud_name and api_key and api_secret)


def cloudinary_browser_upload_enabled() -> bool:
    storage = getattr(settings, 'CLOUDINARY_STORAGE', {})
    cloud_name = (storage.get('CLOUD_NAME') or '').strip()
    upload_preset = (getattr(settings, 'CLOUDINARY_UPLOAD_PRESET', '') or '').strip()
    return bool(cloud_name and upload_preset)


def cloudinary_server_upload_enabled() -> bool:
    return cloudinary_enabled()


def configure_cloudinary() -> None:
    import cloudinary

    storage = settings.CLOUDINARY_STORAGE
    cloudinary.config(
        cloud_name=storage['CLOUD_NAME'],
        api_key=storage['API_KEY'],
        api_secret=storage['API_SECRET'],
        secure=True,
    )


def validate_image_upload(uploaded_file) -> None:
    content_type = (getattr(uploaded_file, 'content_type', '') or '').lower()
    if content_type and content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError('Invalid file type. Only JPG, PNG, GIF, and WebP are allowed.')

    size = getattr(uploaded_file, 'size', 0) or 0
    if size > MAX_IMAGE_BYTES:
        raise ValueError('File size exceeds 10MB limit.')


def is_cloudinary_permission_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return 'forbidden' in message or 'missing permissions' in message or 'actions=["create"]' in message


def is_cloudinary_auth_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return (
        'invalid signature' in message
        or 'api_secret mismatch' in message
        or 'unknown api key' in message
    )


def is_cloudinary_url(url: str) -> bool:
    return 'res.cloudinary.com' in (url or '')


def upload_file_to_cloudinary(uploaded_file, *, folder: str, resource_type: str = 'image') -> dict:
    """Upload via Cloudinary API (requires API key with create/upload permission)."""
    configure_cloudinary()
    import cloudinary.uploader

    if hasattr(uploaded_file, 'seek'):
        uploaded_file.seek(0)

    return cloudinary.uploader.upload(
        uploaded_file,
        folder=folder,
        resource_type=resource_type,
    )


def infer_cloudinary_resource_type(uploaded_file) -> str:
    content_type = (getattr(uploaded_file, 'content_type', '') or '').lower()
    if content_type.startswith('image/'):
        return 'image'
    return 'auto'


def upload_image_to_cloudinary_or_raise(uploaded_file, *, folder: str) -> str:
    """Upload an image to Cloudinary and return the secure URL."""
    if not cloudinary_server_upload_enabled():
        raise ValueError(
            'Cloudinary server upload is unavailable. Configure CLOUDINARY_API_SECRET '
            'or use CLOUDINARY_UPLOAD_PRESET for browser uploads.'
        )

    result = upload_file_to_cloudinary(uploaded_file, folder=folder)
    url = result.get('secure_url') or result.get('url')
    if not url:
        raise ValueError('Cloudinary upload succeeded but no URL was returned')
    return url
