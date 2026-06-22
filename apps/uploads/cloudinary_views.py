"""
Cloudinary upload helpers — credentials stay in backend .env.
"""
from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .cloudinary_folders import (
    cloudinary_chat_folder,
    cloudinary_folder,
    cloudinary_jobs_folder,
    cloudinary_projects_folder,
    cloudinary_services_folder,
    cloudinary_task_attachments_folder,
    cloudinary_uploads_folder,
    cloudinary_users_covers_folder,
    cloudinary_users_profiles_folder,
    cloudinary_site_favicon_folder,
    get_cloudinary_root,
    resolve_cloudinary_folder,
)
from .cloudinary_utils import (
    cloudinary_browser_upload_enabled,
    cloudinary_server_upload_enabled,
    infer_cloudinary_resource_type,
    is_cloudinary_auth_error,
    is_cloudinary_permission_error,
    upload_file_to_cloudinary,
    validate_image_upload,
)


class CloudinaryConfigView(APIView):
    """Public config for browser uploads (unsigned preset only — no secrets)."""

    permission_classes = [AllowAny]

    def get(self, request):
        storage = getattr(settings, 'CLOUDINARY_STORAGE', {})
        cloud_name = (storage.get('CLOUD_NAME') or '').strip()
        upload_preset = (getattr(settings, 'CLOUDINARY_UPLOAD_PRESET', '') or '').strip()
        browser_upload = cloudinary_browser_upload_enabled()
        server_upload = cloudinary_server_upload_enabled()

        return Response(
            {
                'enabled': browser_upload or server_upload,
                'browser_upload': browser_upload,
                'server_upload': server_upload,
                'cloud_name': cloud_name if browser_upload or server_upload else '',
                'upload_preset': upload_preset if browser_upload else '',
                'folder': get_cloudinary_root(),
                'folders': {
                    'users': cloudinary_folder('Users'),
                    'usersProfiles': cloudinary_users_profiles_folder(),
                    'usersCovers': cloudinary_users_covers_folder(),
                    'tasks': cloudinary_folder('Tasks'),
                    'services': cloudinary_services_folder(),
                    'projects': cloudinary_projects_folder(),
                    'jobs': cloudinary_jobs_folder(),
                    'uploads': cloudinary_uploads_folder(),
                    'chat': cloudinary_chat_folder(),
                    'siteFavicon': cloudinary_site_favicon_folder(),
                },
            }
        )


class CloudinaryUploadView(APIView):
    """Server-side image upload to Cloudinary (uses API secret from env)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not cloudinary_server_upload_enabled():
            return Response(
                {
                    'detail': (
                        'Server-side Cloudinary upload is not configured. '
                        'Set CLOUDINARY_API_SECRET correctly or use CLOUDINARY_UPLOAD_PRESET for browser uploads.'
                    ),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        uploaded = request.FILES.get('file') or request.FILES.get('image')
        if not uploaded:
            return Response({'detail': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if infer_cloudinary_resource_type(uploaded) == 'image':
                validate_image_upload(uploaded)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        folder = resolve_cloudinary_folder(request.data.get('folder'))
        resource_type = infer_cloudinary_resource_type(uploaded)

        try:
            result = upload_file_to_cloudinary(uploaded, folder=folder, resource_type=resource_type)
        except Exception as exc:
            if is_cloudinary_auth_error(exc):
                return Response(
                    {
                        'detail': (
                            'Cloudinary API secret does not match the API key. '
                            'Copy the full API secret from Cloudinary Console → Settings → API Keys, '
                            'or use an unsigned CLOUDINARY_UPLOAD_PRESET for browser uploads.'
                        ),
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            if is_cloudinary_permission_error(exc):
                return Response(
                    {
                        'detail': (
                            'Cloudinary API key lacks upload permission. In the Cloudinary Console, '
                            'open Settings → API Keys, assign an upload-capable role (e.g. Master Admin) '
                            'to your key, or set CLOUDINARY_UPLOAD_PRESET for unsigned browser uploads.'
                        ),
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            raise

        return Response(
            {
                'url': result.get('secure_url') or result.get('url'),
                'public_id': result.get('public_id'),
                'width': result.get('width'),
                'height': result.get('height'),
            },
            status=status.HTTP_201_CREATED,
        )
