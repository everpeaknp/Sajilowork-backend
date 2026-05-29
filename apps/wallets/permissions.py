from rest_framework import permissions


class IsWalletOwner(permissions.BasePermission):
    """
    Permission to only allow wallet owners to access their wallet
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin can access all wallets
        if request.user.is_staff:
            return True
        
        # User can only access their own wallet
        return obj.user == request.user


class IsTransactionOwner(permissions.BasePermission):
    """
    Permission to only allow transaction owners to view their transactions
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin can access all transactions
        if request.user.is_staff:
            return True
        
        # User can only access their own transactions
        return obj.wallet.user == request.user


class IsWithdrawalOwner(permissions.BasePermission):
    """
    Permission to only allow withdrawal request owners to access their requests
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin can access all withdrawal requests
        if request.user.is_staff:
            return True
        
        # User can only access their own withdrawal requests
        return obj.wallet.user == request.user
