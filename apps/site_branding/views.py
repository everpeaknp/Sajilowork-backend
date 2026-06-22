from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import get_public_site_settings


class SiteSettingsAPIView(APIView):
    """Public site name and favicon configured in Django admin."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(get_public_site_settings(request=request))
