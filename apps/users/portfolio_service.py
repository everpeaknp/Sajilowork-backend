"""
Portfolio uploads: file storage and UserDocument sync for admin review.
"""
import os
import uuid
from urllib.parse import urlparse

from django.conf import settings
from django.core.files.storage import default_storage

from apps.uploads.cloudinary_folders import cloudinary_users_portfolio_folder
from apps.uploads.cloudinary_utils import (
    cloudinary_enabled,
    infer_cloudinary_resource_type,
    is_cloudinary_url,
    upload_file_to_cloudinary,
)

from .models import PortfolioItem, UserDocument

PORTFOLIO_DOCUMENT_TYPE = 'portfolio'
MAX_PORTFOLIO_ITEMS = 30
ALLOWED_PORTFOLIO_CONTENT_TYPES = {
    'image/jpeg',
    'image/png',
    'application/pdf',
    'text/plain',
}
MAX_PORTFOLIO_BYTES = 5 * 1024 * 1024


def portfolio_document_number(portfolio_item_id) -> str:
    return f'portfolio:{portfolio_item_id}'


def portfolio_item_id_from_document_number(document_number: str) -> str | None:
    if not document_number or not document_number.startswith('portfolio:'):
        return None
    raw = document_number.split('|')[0].replace('portfolio:', '', 1).strip()
    return raw or None


def save_portfolio_upload(user, uploaded_file) -> str:
    """Persist portfolio file to Cloudinary or local media; return stored URL/path."""
    folder = cloudinary_users_portfolio_folder(user.id)
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
    relative_path = f'portfolio/{user.id}/{filename}'
    return default_storage.save(relative_path, uploaded_file)


def resolve_portfolio_stored_url(request, stored_value: str) -> str:
    if not stored_value:
        return stored_value
    if is_cloudinary_url(stored_value) or stored_value.startswith('http://') or stored_value.startswith('https://'):
        return stored_value
    return build_portfolio_file_url(request, stored_value)


def build_portfolio_file_url(request, storage_path: str) -> str:
    if is_cloudinary_url(storage_path) or storage_path.startswith('http://') or storage_path.startswith('https://'):
        return storage_path
    media_url = default_storage.url(storage_path)
    if media_url.startswith('http://') or media_url.startswith('https://'):
        return media_url
    return request.build_absolute_uri(media_url)


def resolve_portfolio_file_url(request, stored_url: str) -> str:
    if not stored_url:
        return stored_url
    if is_cloudinary_url(stored_url) or stored_url.startswith('http://') or stored_url.startswith('https://'):
        return stored_url
    return request.build_absolute_uri(stored_url) if request else stored_url


def storage_path_from_file_url(file_url: str) -> str | None:
    if not file_url:
        return None
    path = urlparse(file_url).path
    media_prefix = settings.MEDIA_URL
    if not path.startswith(media_prefix):
        return None
    return path[len(media_prefix) :].lstrip('/')


def sync_portfolio_user_document(user, portfolio_item: PortfolioItem, *, document_url: str) -> UserDocument:
    return UserDocument.objects.update_or_create(
        user=user,
        document_type=PORTFOLIO_DOCUMENT_TYPE,
        document_number=portfolio_document_number(portfolio_item.id),
        defaults={
            'document_url': document_url,
            'status': 'pending',
            'rejection_reason': '',
            'verified_at': None,
            'verified_by': None,
        },
    )[0]


def delete_portfolio_user_document(user, portfolio_item_id) -> None:
    UserDocument.objects.filter(
        user=user,
        document_type=PORTFOLIO_DOCUMENT_TYPE,
        document_number=portfolio_document_number(portfolio_item_id),
    ).delete()


def delete_portfolio_file(file_url: str) -> None:
    relative = storage_path_from_file_url(file_url)
    if relative and default_storage.exists(relative):
        default_storage.delete(relative)


def portfolio_document_status_map(user) -> dict[str, UserDocument]:
    """Map portfolio item id (str) -> UserDocument."""
    result: dict[str, UserDocument] = {}
    for doc in UserDocument.objects.filter(user=user, document_type=PORTFOLIO_DOCUMENT_TYPE):
        item_id = portfolio_item_id_from_document_number(doc.document_number)
        if item_id:
            result[item_id] = doc
    return result


def get_public_portfolio_items(user):
    """
    Public profile: approved portfolio items, plus legacy items without a linked document.
    """
    items = list(PortfolioItem.objects.filter(user=user))
    doc_map = portfolio_document_status_map(user)
    visible = []
    for item in items:
        doc = doc_map.get(str(item.id))
        if doc is None or doc.status == 'approved':
            visible.append(item)
    return visible
