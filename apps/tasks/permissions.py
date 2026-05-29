"""
Custom permissions for Tasks app.
"""
from rest_framework import permissions


class IsTaskOwner(permissions.BasePermission):
    """
    Permission to only allow task owners to edit/delete tasks.
    """
    
    message = 'You must be the task owner to perform this action.'
    
    def has_object_permission(self, request, view, obj):
        """Check if user is the task owner."""
        return obj.owner == request.user


class IsTaskOwnerOrReadOnly(permissions.BasePermission):
    """
    Permission to allow read-only access to everyone,
    but write access only to the task owner.
    """
    
    def has_object_permission(self, request, view, obj):
        """Check permissions."""
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.owner == request.user


class IsTaskOwnerOrAssignedTasker(permissions.BasePermission):
    """
    Permission for task owner or assigned tasker.
    """
    
    message = 'You must be the task owner or assigned tasker to perform this action.'
    
    def has_object_permission(self, request, view, obj):
        """Check if user is owner or assigned tasker."""
        return obj.owner == request.user or obj.assigned_tasker == request.user


class CanBidOnTask(permissions.BasePermission):
    """
    Permission to check if user can bid on a task.
    """
    
    message = 'You cannot bid on this task.'
    
    def has_object_permission(self, request, view, obj):
        """Check if user can bid."""
        # Cannot bid on own task
        if obj.owner == request.user:
            return False
        
        # Task must be open
        if obj.status != 'open':
            return False
        
        # Bidding must be allowed
        if not obj.allow_bids:
            return False
        
        # User must be a tasker
        if request.user.role != 'tasker':
            return False
        
        return True
