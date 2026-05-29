import json

from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from .services import ModerationService


class AccountSuspensionMiddleware(MiddlewareMixin):
    """Return 403 for mutating API calls while the user is suspended."""

    SAFE_PREFIXES = (
        '/api/v1/auth/',
        '/api/v1/rules/',
        '/admin/',
    )

    def process_request(self, request):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return None
        if not request.path.startswith('/api/'):
            return None
        if any(request.path.startswith(p) for p in self.SAFE_PREFIXES):
            return None
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return None
        if ModerationService.is_user_suspended(user):
            user = ModerationService.refresh_suspension_state(user)
            if user.account_suspended:
                return JsonResponse(
                    {
                        'error': (
                            'Your account is temporarily suspended due to repeated task cancellations.'
                        ),
                        'suspended_until': (
                            user.suspended_until.isoformat() if user.suspended_until else None
                        ),
                        'reason': user.suspension_reason,
                    },
                    status=403,
                )
        return None
