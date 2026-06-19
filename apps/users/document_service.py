import os
import uuid
from urllib.parse import urlparse

from django.conf import settings
from django.core.files.storage import default_storage

from apps.uploads.cloudinary_folders import cloudinary_users_documents_folder
from apps.uploads.cloudinary_utils import (
    cloudinary_enabled,
    infer_cloudinary_resource_type,
    is_cloudinary_url,
    upload_file_to_cloudinary,
)

from .models import UserDocument

MAX_DOCUMENT_BYTES = 5 * 1024 * 1024
ALLOWED_DOCUMENT_CONTENT_TYPES = {
    'image/jpeg',
    'image/png',
    'application/pdf',
}


def save_user_document_upload(user, uploaded_file) -> str:
    """Persist document to Cloudinary or local media; return stored URL/path."""
    folder = cloudinary_users_documents_folder(user.id)
    if cloudinary_enabled():
        try:
            result = upload_file_to_cloudinary(
                uploaded_file,
                folder=folder,
                resource_type=infer_cloudinary_resource_type(uploaded_file),
            )
            url = result.get('secure_url') or result.get('url')
            if url:
                return url
        except Exception:
            pass

    ext = os.path.splitext(uploaded_file.name)[1].lower() or ''
    filename = f'{uuid.uuid4().hex}{ext}'
    relative_path = f'user_documents/{user.id}/{filename}'
    return default_storage.save(relative_path, uploaded_file)


def build_document_url(request, storage_path: str) -> str:
    if is_cloudinary_url(storage_path) or storage_path.startswith('http://') or storage_path.startswith('https://'):
        return storage_path
    media_url = default_storage.url(storage_path)
    if media_url.startswith('http://') or media_url.startswith('https://'):
        return media_url
    return request.build_absolute_uri(media_url)


def resolve_document_url(request, stored_url: str) -> str:
    if not stored_url:
        return stored_url
    if is_cloudinary_url(stored_url) or stored_url.startswith('http://') or stored_url.startswith('https://'):
        return stored_url
    return request.build_absolute_uri(stored_url) if request else stored_url


def storage_path_from_document_url(document_url: str) -> str | None:
    if not document_url:
        return None
    path = urlparse(document_url).path
    media_prefix = settings.MEDIA_URL
    if not path.startswith(media_prefix):
        return None
    return path[len(media_prefix) :].lstrip('/')


def delete_document_file(document_url: str) -> None:
    relative = storage_path_from_document_url(document_url)
    if relative and default_storage.exists(relative):
        default_storage.delete(relative)


def upsert_user_document(
    *,
    user,
    document_type: str,
    document_url: str,
    document_number: str = '',
) -> UserDocument:
    """
    Upsert a single document per user+document_type.
    Resets verification fields to pending for replacements.
    """
    doc, _ = UserDocument.objects.update_or_create(
        user=user,
        document_type=document_type,
        defaults={
            'document_url': document_url,
            'document_number': document_number or '',
            'status': 'pending',
            'rejection_reason': '',
            'verified_at': None,
            'verified_by': None,
        },
    )
    return doc

