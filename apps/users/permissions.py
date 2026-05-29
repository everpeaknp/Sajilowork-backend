"""
Custom permissions for User app.
"""
from rest_framework import permissions


class IsOwner(permissions.BasePermission):
    """
    Permission to only allow owners of an object to edit it.
    """
    
    def has_object_permission(self, request, view, obj):
        """Check if user is the owner."""
        return obj == request.user


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Permission to allow read-only access to everyone,
    but write access only to the owner.
    """
    
    def has_object_permission(self, request, view, obj):
        """Check permissions."""
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj == request.user


class IsTasker(permissions.BasePermission):
    """
    Permission to only allow taskers.
    """
    
    message = 'Only taskers can perform this action.'
    
    def has_permission(self, request, view):
        """Check if user is a tasker."""
        return request.user and request.user.is_authenticated and request.user.role == 'tasker'


class IsCustomer(permissions.BasePermission):
    """
    Permission to only allow customers.
    """
    
    message = 'Only customers can perform this action.'
    
    def has_permission(self, request, view):
        """Check if user is a customer."""
        return request.user and request.user.is_authenticated and request.user.role == 'customer'


class IsVerifiedTasker(permissions.BasePermission):
    """
    Permission to only allow verified taskers.
    """
    
    message = 'Only verified taskers can perform this action.'
    
    def has_permission(self, request, view):
        """Check if user is a verified tasker."""
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role == 'tasker' and 
            request.user.is_verified_tasker
        )


class IsAdminUser(permissions.BasePermission):
    """
    Permission to only allow admin users.
    """
    
    message = 'Only admin users can perform this action.'
    
    def has_permission(self, request, view):
        """Check if user is an admin."""
        return request.user and request.user.is_authenticated and request.user.role == 'admin'
