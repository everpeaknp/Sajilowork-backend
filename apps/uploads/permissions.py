"""
Uploads Permissions
"""
from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an upload to edit/delete it.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            # For public uploads, allow read access
            if hasattr(obj, 'is_public') and obj.is_public:
                return True
            # For private uploads, only owner can read
            return obj.user == request.user
        
        # Write permissions are only allowed to the owner
        return obj.user == request.user


class IsOwner(permissions.BasePermission):
    """
    Custom permission to only allow owners of an upload to access it.
    """
    
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user
