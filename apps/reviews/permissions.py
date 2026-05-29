"""Review permissions — creation is validated in ReviewService."""
from rest_framework import permissions


class IsReviewAuthor(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.reviewer == request.user
