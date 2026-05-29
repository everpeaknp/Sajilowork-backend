from rest_framework import permissions


class IsPaymentParticipant(permissions.BasePermission):
    """
    Permission to check if user is payer or payee of the payment
    """
    
    def has_object_permission(self, request, view, obj):
        return obj.payer == request.user or obj.payee == request.user


class IsPaymentMethodOwner(permissions.BasePermission):
    """
    Permission to check if user owns the payment method
    """
    
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


class IsRefundAuthorized(permissions.BasePermission):
    """
    Permission to check if user can create/view refund
    """
    
    def has_object_permission(self, request, view, obj):
        # User must be payer, payee, or admin
        return (
            obj.payment.payer == request.user or
            obj.payment.payee == request.user or
            request.user.is_staff
        )


class IsPayoutOwner(permissions.BasePermission):
    """
    Permission to check if user owns the payout
    """
    
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Permission to allow read-only access to all users, write access to admins only
    """
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff
