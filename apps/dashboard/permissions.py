"""
Custom permissions for Dashboard app.
"""
from rest_framework import permissions


class IsAdminUser(permissions.BasePermission):
    """
    Permission to only allow admin users to access dashboard.
    """
    
    message = 'Only admin users can access the dashboard.'
    
    def has_permission(self, request, view):
        """Check if user is an admin."""
        return (
            request.user and 
            request.user.is_authenticated and 
            (request.user.role == 'admin' or request.user.is_staff or request.user.is_superuser)
        )


class IsAuthenticatedUser(permissions.BasePermission):
    """
    Permission to allow authenticated users to view their own stats.
    """
    
    message = 'Authentication required.'
    
    def has_permission(self, request, view):
        """Check if user is authenticated."""
        return request.user and request.user.is_authenticated
