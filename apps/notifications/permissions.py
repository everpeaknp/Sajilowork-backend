"""
Notifications App Permissions
"""
from rest_framework import permissions


class IsNotificationRecipient(permissions.BasePermission):
    """
    Permission to check if user is the notification recipient
    """
    def has_object_permission(self, request, view, obj):
        return obj.recipient == request.user


class IsNotificationOwner(permissions.BasePermission):
    """
    Permission to check if user owns the notification preference/device token
    """
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Permission to allow read-only access to all users, but write access only to admins
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff
