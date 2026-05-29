"""
Task attachment uploads: store files under media and build absolute URLs.
"""
import os
import uuid

from django.core.files.storage import default_storage

MAX_TASK_ATTACHMENT_BYTES = 10 * 1024 * 1024
ALLOWED_TASK_ATTACHMENT_CONTENT_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/gif',
}


def save_task_attachment_upload(user, task, uploaded_file) -> str:
    """Persist file under media/task_attachments/<task_id>/ and return storage path."""
    ext = os.path.splitext(uploaded_file.name)[1].lower() or ''
    filename = f'{uuid.uuid4().hex}{ext}'
    relative_path = f'task_attachments/{task.id}/{filename}'
    return default_storage.save(relative_path, uploaded_file)


def build_task_attachment_file_url(request, storage_path: str) -> str:
    media_url = default_storage.url(storage_path)
    if media_url.startswith('http://') or media_url.startswith('https://'):
        return media_url
    return request.build_absolute_uri(media_url)


def classify_task_attachment_type(content_type: str, filename: str) -> str:
    """Map upload to TaskAttachment.FILE_TYPES choice values."""
    ct = (content_type or '').lower()
    if ct.startswith('image/'):
        return 'image'
    name = (filename or '').lower()
    if name.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')):
        return 'image'
    if name.endswith(('.pdf', '.doc', '.docx', '.txt')):
        return 'document'
    if name.endswith(('.mp4', '.mov', '.webm', '.avi')):
        return 'video'
    return 'other'
