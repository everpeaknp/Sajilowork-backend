"""
Task attachment uploads: Cloudinary when configured, local media as fallback.
"""
import os
import uuid

from django.conf import settings
from django.core.files.storage import default_storage

from apps.tasks.listing import (
    LISTING_KIND_JOB,
    LISTING_KIND_PROJECT,
    LISTING_KIND_SERVICE,
    get_listing_kind,
)
from apps.uploads.cloudinary_folders import (
    cloudinary_jobs_folder,
    cloudinary_projects_folder,
    cloudinary_services_folder,
    cloudinary_task_attachments_folder,
)
from apps.uploads.cloudinary_utils import (
    cloudinary_enabled,
    infer_cloudinary_resource_type,
    is_cloudinary_permission_error,
    is_cloudinary_url,
    upload_file_to_cloudinary,
)

MAX_TASK_ATTACHMENT_BYTES = 10 * 1024 * 1024

ALLOWED_TASK_ATTACHMENT_CONTENT_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/gif',
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}

ALLOWED_TASK_ATTACHMENT_EXTENSIONS = {
    '.jpg',
    '.jpeg',
    '.png',
    '.webp',
    '.gif',
    '.pdf',
    '.doc',
    '.docx',
}

TASK_ATTACHMENT_TYPE_ERROR = (
    'Invalid file type. Only JPG, PNG, WEBP, GIF, PDF, DOC, and DOCX files are allowed.'
)


def _cloudinary_folder_for_task(task) -> str:
    kind = get_listing_kind(getattr(task, 'tags', None))
    if kind == LISTING_KIND_PROJECT:
        return cloudinary_projects_folder()
    if kind == LISTING_KIND_SERVICE:
        return cloudinary_services_folder()
    if kind == LISTING_KIND_JOB:
        return cloudinary_jobs_folder()
    return cloudinary_task_attachments_folder(task.id)


def save_task_attachment_upload(user, task, uploaded_file) -> str:
    """
    Store attachment and return a public URL.
    Prefers Cloudinary for all allowed file types when configured.
    """
    filename = uploaded_file.name or 'attachment'

    if cloudinary_enabled():
        folder = _cloudinary_folder_for_task(task)
        try:
            result = upload_file_to_cloudinary(
                uploaded_file,
                folder=folder,
                resource_type=infer_cloudinary_resource_type(uploaded_file),
            )
            url = result.get('secure_url') or result.get('url')
            if url:
                return url
        except Exception as exc:
            if not is_cloudinary_permission_error(exc):
                raise

    ext = os.path.splitext(filename)[1].lower() or ''
    storage_name = f'{uuid.uuid4().hex}{ext}'
    relative_path = f'task_attachments/{task.id}/{storage_name}'
    saved_path = default_storage.save(relative_path, uploaded_file)
    return build_task_attachment_file_url(None, saved_path)


def resolve_task_attachment_file_url(request, stored_value: str) -> str:
    """Normalize stored path or absolute URL to a browser-ready URL."""
    if not stored_value:
        return ''
    if stored_value.startswith('http://') or stored_value.startswith('https://'):
        return stored_value
    return build_task_attachment_file_url(request, stored_value)


def build_task_attachment_file_url(request, storage_path: str) -> str:
    media_url = default_storage.url(storage_path)
    if media_url.startswith('http://') or media_url.startswith('https://'):
        return media_url
    if request is not None:
        return request.build_absolute_uri(media_url)
    return media_url


def classify_task_attachment_type(content_type: str, filename: str) -> str:
    """Map upload to TaskAttachment.FILE_TYPES choice values."""
    ct = (content_type or '').lower()
    if ct.startswith('image/'):
        return 'image'
    if ct in (
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ):
        return 'document'
    name = (filename or '').lower()
    if name.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')):
        return 'image'
    if name.endswith(('.pdf', '.doc', '.docx', '.txt')):
        return 'document'
    if name.endswith(('.mp4', '.mov', '.webm', '.avi')):
        return 'video'
    return 'other'


def is_allowed_task_attachment(content_type: str, filename: str) -> bool:
    """Accept known MIME types or trusted extensions (e.g. octet-stream uploads)."""
    ct = (content_type or '').lower()
    if ct in ALLOWED_TASK_ATTACHMENT_CONTENT_TYPES:
        return True
    ext = os.path.splitext(filename or '')[1].lower()
    if ext in ALLOWED_TASK_ATTACHMENT_EXTENSIONS:
        return True
    return False


def validate_cloudinary_attachment_url(file_url: str) -> None:
    if not is_cloudinary_url(file_url):
        raise ValueError('Invalid file URL. Only Cloudinary URLs are accepted.')
