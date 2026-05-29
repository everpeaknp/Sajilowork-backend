"""
Custom permissions for chat app.
"""
from rest_framework import permissions


class IsConversationParticipant(permissions.BasePermission):
    """
    Permission to check if user is a participant in the conversation.
    """
    
    def has_object_permission(self, request, view, obj):
        # For Message objects, check conversation participants
        if hasattr(obj, 'conversation'):
            return obj.conversation.participants.filter(id=request.user.id).exists()
        
        # For Conversation objects, check participants directly
        if hasattr(obj, 'participants'):
            return obj.participants.filter(id=request.user.id).exists()
        
        return False


class IsMessageSender(permissions.BasePermission):
    """
    Permission to check if user is the sender of the message.
    """
    
    def has_object_permission(self, request, view, obj):
        # Only allow sender to edit/delete their own messages
        if hasattr(obj, 'sender'):
            return obj.sender == request.user
        return False


class IsReportOwnerOrAdmin(permissions.BasePermission):
    """
    Permission to check if user is the report owner or an admin.
    """
    
    def has_object_permission(self, request, view, obj):
        # Admins can view all reports
        if request.user.role == 'admin':
            return True
        
        # Users can only view their own reports
        if hasattr(obj, 'reported_by'):
            return obj.reported_by == request.user
        
        return False
