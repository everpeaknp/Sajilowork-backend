from rest_framework import permissions

from .services import ModerationService


class NotSuspended(permissions.BasePermission):
    """Block write actions while account is under moderation suspension."""

    message = (
        'Your account is temporarily suspended due to repeated task cancellations. '
        'Please try again after the suspension period ends.'
    )

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return True
        if request.method in permissions.SAFE_METHODS:
            return True
        return not ModerationService.is_user_suspended(request.user)
