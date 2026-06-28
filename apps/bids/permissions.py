"""
Custom permissions for Bids app.
"""
from rest_framework import permissions


class IsBidParticipant(permissions.BasePermission):
    """
    Tasker, task owner, staff, or (read-only) viewers of bids on public tasks.
    """

    message = 'You are not allowed to access this bid.'

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or getattr(user, 'is_admin', False):
            return True
        if obj.tasker == user or obj.task.owner == user:
            return True
        if view.action == 'retrieve' and obj.task.is_public:
            return True
        return False


class IsBidOwner(permissions.BasePermission):
    """
    Permission to check if user is the bid owner (tasker who submitted the bid).
    """
    
    message = "You must be the bid owner to perform this action."
    
    def has_object_permission(self, request, view, obj):
        """Check if user is the bid owner."""
        return obj.tasker == request.user


class IsTaskOwner(permissions.BasePermission):
    """
    Permission to check if user is the task owner.
    """
    
    message = "You must be the task owner to perform this action."
    
    def has_object_permission(self, request, view, obj):
        """Check if user is the task owner."""
        # obj is a Bid instance
        return obj.task.owner == request.user


class CanAcceptBid(permissions.BasePermission):
    """
    Permission to check if user can accept a bid.
    Only task owner can accept bids on their tasks.
    """
    
    message = "Only the task owner can accept bids."
    
    def has_object_permission(self, request, view, obj):
        """Check if user can accept the bid."""
        # Must be task owner
        if obj.task.owner != request.user:
            return False
        
        # Bid must be pending
        if obj.status != 'pending':
            self.message = "Only pending bids can be accepted."
            return False
        
        # Task must be open or draft (matches BidWorkflowService)
        if obj.task.status not in ('open', 'draft'):
            self.message = (
                f"Task is not open for bid acceptance (current status: {obj.task.status})."
            )
            return False

        # Only one accepted offer per task
        if obj.task.bids.filter(status='accepted').exists():
            self.message = "This task already has an accepted offer."
            return False
        
        return True


class CanRejectBid(permissions.BasePermission):
    """
    Permission to check if user can reject a bid.
    Only task owner can reject bids on their tasks.
    """
    
    message = "Only the task owner can reject bids."
    
    def has_object_permission(self, request, view, obj):
        """Check if user can reject the bid."""
        # Must be task owner
        if obj.task.owner != request.user:
            return False
        
        # Bid must be pending
        if obj.status != 'pending':
            self.message = "Only pending bids can be rejected."
            return False
        
        return True


class CanWithdrawBid(permissions.BasePermission):
    """
    Permission to check if user can withdraw a bid.
    Only bid owner can withdraw their own bids.
    """
    
    message = "Only the bid owner can withdraw their bid."
    
    def has_object_permission(self, request, view, obj):
        """Check if user can withdraw the bid."""
        # Must be bid owner
        if obj.tasker != request.user:
            return False
        
        # Bid must be pending
        if obj.status != 'pending':
            self.message = "Only pending bids can be withdrawn."
            return False
        
        return True


class CanCreateCounterOffer(permissions.BasePermission):
    """
    Permission to check if user can create a counter offer.
    Only task owner can create counter offers.
    """
    
    message = "Only the task owner can create counter offers."
    
    def has_object_permission(self, request, view, obj):
        """Check if user can create counter offer."""
        # Must be task owner
        if obj.task.owner != request.user:
            return False
        
        # Bid must be pending
        if obj.status != 'pending':
            self.message = "Can only create counter offers for pending bids."
            return False
        
        return True


class CanSendBidMessage(permissions.BasePermission):
    """
    Permission to check if user can send messages on a bid.
    Both task owner and bid owner can send messages.
    """
    
    message = "You must be involved in this bid to send messages."
    
    def has_permission(self, request, view):
        """Check if user can send messages."""
        if request.method == 'POST':
            bid_id = request.data.get('bid')
            if not bid_id:
                return False
            
            from .models import Bid
            try:
                bid = Bid.objects.get(id=bid_id)
                return request.user in [bid.tasker, bid.task.owner]
            except Bid.DoesNotExist:
                return False
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """Check if user can access the message."""
        # obj is a BidMessage instance
        return request.user in [obj.bid.tasker, obj.bid.task.owner]


class CanReviewBid(permissions.BasePermission):
    """
    Permission to check if user can review a bid.
    Only task owner can review bids.
    """
    
    message = "Only the task owner can review bids."
    
    def has_permission(self, request, view):
        """Check if user can create a review."""
        if request.method == 'POST':
            bid_id = request.data.get('bid')
            if not bid_id:
                return False
            
            from .models import Bid
            try:
                bid = Bid.objects.get(id=bid_id)
                return bid.task.owner == request.user
            except Bid.DoesNotExist:
                return False
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """Check if user can access the review."""
        # obj is a BidReview instance
        return request.user in [obj.bid.tasker, obj.bid.task.owner]
