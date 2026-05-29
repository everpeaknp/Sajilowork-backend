"""
Custom permissions for Locations app.
"""
from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Permission to allow read-only access to everyone,
    but write access only to the owner.
    """
    
    def has_object_permission(self, request, view, obj):
        """Check permissions"""
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user == request.user


class IsOwner(permissions.BasePermission):
    """
    Permission to only allow owners of an object to access it.
    """
    
    def has_object_permission(self, request, view, obj):
        """Check if user is the owner"""
        return obj.user == request.user


class IsTaskerForServiceArea(permissions.BasePermission):
    """
    Permission to only allow taskers to manage service areas.
    """
    
    message = 'Only taskers can manage service areas.'
    
    def has_permission(self, request, view):
        """Check if user is a tasker for create/list actions"""
        if request.method in permissions.SAFE_METHODS:
            return True
        
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role == 'tasker'
        )
    
    def has_object_permission(self, request, view, obj):
        """Check if user owns the service area"""
        if request.method in permissions.SAFE_METHODS:
            return True
        
        return obj.user == request.user and request.user.role == 'tasker'


class IsAdminUser(permissions.BasePermission):
    """
    Permission to only allow admin users.
    """
    
    message = 'Only admin users can perform this action.'
    
    def has_permission(self, request, view):
        """Check if user is an admin"""
        return (
            request.user and 
            request.user.is_authenticated and 
            (request.user.is_staff or request.user.role == 'admin')
        )
