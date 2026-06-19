"""
Cloudinary media folder layout.

All uploads live under CLOUDINARY_DEFAULT_FOLDER (default: Sajilowork), for example:

    Sajilowork/
      Users/Profiles/
      Users/Covers/
      Tasks/{task_id}/
      Services/
      Projects/
      Jobs/
      Uploads/
      Chat/
"""
from django.conf import settings

DEFAULT_CLOUDINARY_ROOT = 'Sajilowork'


def get_cloudinary_root() -> str:
    configured = getattr(settings, 'CLOUDINARY_DEFAULT_FOLDER', None)
    root = (configured or DEFAULT_CLOUDINARY_ROOT).strip().strip('/')
    return root or DEFAULT_CLOUDINARY_ROOT


def cloudinary_folder(*segments: str) -> str:
    parts = [get_cloudinary_root()]
    for segment in segments:
        cleaned = str(segment).strip().strip('/')
        if cleaned:
            parts.append(cleaned)
    return '/'.join(parts)


def resolve_cloudinary_folder(requested: str | None) -> str:
    """
    Normalize a folder from the client. Shorthand paths like Users/Profiles are
    always stored under the configured root folder.
    """
    root = get_cloudinary_root()
    if not requested or not str(requested).strip():
        return root

    folder = str(requested).strip().strip('/')
    if folder == root or folder.startswith(f'{root}/'):
        return folder
    return cloudinary_folder(folder)


def cloudinary_users_profiles_folder() -> str:
    return cloudinary_folder('Users', 'Profiles')


def cloudinary_users_covers_folder() -> str:
    return cloudinary_folder('Users', 'Covers')


def cloudinary_task_attachments_folder(task_id) -> str:
    return cloudinary_folder('Tasks', str(task_id))


def cloudinary_services_folder() -> str:
    return cloudinary_folder('Services')


def cloudinary_projects_folder() -> str:
    return cloudinary_folder('Projects')


def cloudinary_jobs_folder() -> str:
    return cloudinary_folder('Jobs')


def cloudinary_uploads_folder() -> str:
    return cloudinary_folder('Uploads')


def cloudinary_chat_folder() -> str:
    return cloudinary_folder('Chat')
