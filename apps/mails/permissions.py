"""
Custom permissions for Email Management
"""
from rest_framework.permissions import BasePermission


class IsSuperUserForSMTP(BasePermission):
    """
    Only superusers can modify SMTP settings
    """
    def has_permission(self, request, view):
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return request.user.is_staff
        # PUT, PATCH, DELETE require superuser
        return request.user.is_superuser


class IsStaffForTemplates(BasePermission):
    """
    Staff users can manage templates
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class IsStaffForEmailManagement(BasePermission):
    """
    Staff users can access email management features
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class IsSuperUserForDeletion(BasePermission):
    """
    Only superusers can delete templates and configurations
    """
    def has_permission(self, request, view):
        if request.method == 'DELETE':
            return request.user.is_superuser
        return request.user.is_staff
