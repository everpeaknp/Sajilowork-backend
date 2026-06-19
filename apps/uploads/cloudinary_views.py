"""
Cloudinary upload helpers — credentials stay in backend .env.
"""
from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .cloudinary_utils import (
    cloudinary_enabled,
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
        enabled = cloudinary_enabled()

        return Response(
            {
                'enabled': enabled,
                'cloud_name': cloud_name if enabled else '',
                'upload_preset': upload_preset if enabled and upload_preset else '',
                'folder': getattr(settings, 'CLOUDINARY_DEFAULT_FOLDER', 'sajilowork'),
            }
        )


class CloudinaryUploadView(APIView):
    """Server-side image upload to Cloudinary (uses API secret from env)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not cloudinary_enabled():
            return Response(
                {'detail': 'Cloudinary is not configured on the server.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        uploaded = request.FILES.get('file') or request.FILES.get('image')
        if not uploaded:
            return Response({'detail': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_image_upload(uploaded)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        folder = (request.data.get('folder') or getattr(settings, 'CLOUDINARY_DEFAULT_FOLDER', 'sajilowork')).strip()

        try:
            result = upload_file_to_cloudinary(uploaded, folder=folder)
        except Exception as exc:
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
