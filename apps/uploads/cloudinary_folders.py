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


def cloudinary_employers_logo_folder(user_id) -> str:
    return cloudinary_folder('Employers', str(user_id), 'Logos')


def cloudinary_employers_gallery_folder(user_id) -> str:
    return cloudinary_folder('Employers', str(user_id), 'Gallery')


def cloudinary_users_portfolio_folder(user_id) -> str:
    return cloudinary_folder('Users', str(user_id), 'Portfolio')


def cloudinary_users_documents_folder(user_id) -> str:
    return cloudinary_folder('Users', str(user_id), 'Documents')


def cloudinary_users_badges_folder(user_id) -> str:
    return cloudinary_folder('Users', str(user_id), 'Badges')


def cloudinary_site_favicon_folder() -> str:
    return cloudinary_folder('Site', 'Favicon')


def cloudinary_site_logo_folder() -> str:
    return cloudinary_folder('Site', 'Logo')


def cloudinary_site_og_folder() -> str:
    return cloudinary_folder('Site', 'OG')
