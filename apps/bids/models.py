"""
Bid models for the Airtasker marketplace.
"""
import uuid
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class Bid(models.Model):
    """
    Bid/Offer model for tasks.
    Taskers submit bids to work on tasks.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
        ('expired', 'Expired'),
    ]
    
    # Primary fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.CASCADE,
        related_name='bids'
    )
    tasker = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='submitted_bids'
    )
    
    # Bid details
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    currency = models.CharField(max_length=3, default='NPR')
    proposal = models.TextField(help_text="Detailed proposal for the task")
    estimated_duration = models.PositiveIntegerField(
        help_text="Estimated duration in hours",
        null=True,
        blank=True
    )
    estimated_completion_date = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    
    # Rejection/withdrawal reason
    rejection_reason = models.TextField(blank=True)
    withdrawal_reason = models.TextField(blank=True)
    
    # Counter offer tracking
    is_counter_offer = models.BooleanField(default=False)
    original_bid = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='counter_offers'
    )
    
    # Metadata
    cover_letter = models.TextField(blank=True, help_text="Cover letter/introduction")
    attachments = models.JSONField(default=list, blank=True, help_text="List of attachment URLs")
    
    class Meta:
        db_table = 'bids'
        ordering = ['-created_at']
        unique_together = ['task', 'tasker']  # One bid per tasker per task
        indexes = [
            models.Index(fields=['task', 'status']),
            models.Index(fields=['tasker', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Bid by {self.tasker.get_full_name()} on {self.task.title}"
    
    @property
    def is_pending(self):
        """Check if bid is pending."""
        return self.status == 'pending'
    
    @property
    def is_accepted(self):
        """Check if bid is accepted."""
        return self.status == 'accepted'
    
    @property
    def is_rejected(self):
        """Check if bid is rejected."""
        return self.status == 'rejected'
    
    def accept(self):
        """Accept the bid and assign task to tasker."""
        if self.status != 'pending':
            raise ValueError("Only pending bids can be accepted.")
        
        # Update bid status
        self.status = 'accepted'
        self.accepted_at = timezone.now()
        self.save(update_fields=['status', 'accepted_at'])
        
        # Assign task to tasker
        self.task.assign_to_tasker(self.tasker)
        
        # Reject all other pending bids
        Bid.objects.filter(
            task=self.task,
            status='pending'
        ).exclude(id=self.id).update(
            status='rejected',
            rejected_at=timezone.now(),
            rejection_reason='Another bid was accepted'
        )
    
    def reject(self, reason=''):
        """Reject the bid."""
        if self.status != 'pending':
            raise ValueError("Only pending bids can be rejected.")
        
        self.status = 'rejected'
        self.rejected_at = timezone.now()
        self.rejection_reason = reason
        self.save(update_fields=['status', 'rejected_at', 'rejection_reason'])
    
    def withdraw(self, reason=''):
        """Withdraw the bid."""
        if self.status != 'pending':
            raise ValueError("Only pending bids can be withdrawn.")
        
        self.status = 'withdrawn'
        self.withdrawn_at = timezone.now()
        self.withdrawal_reason = reason
        self.save(update_fields=['status', 'withdrawn_at', 'withdrawal_reason'])
    
    def create_counter_offer(self, new_amount, new_proposal):
        """Create a counter offer from task owner."""
        counter_bid = Bid.objects.create(
            task=self.task,
            tasker=self.tasker,
            amount=new_amount,
            currency=self.currency,
            proposal=new_proposal,
            estimated_duration=self.estimated_duration,
            estimated_completion_date=self.estimated_completion_date,
            is_counter_offer=True,
            original_bid=self
        )
        
        # Mark original bid as rejected
        self.reject(reason='Counter offer sent')
        
        return counter_bid


class BidMessage(models.Model):
    """
    Messages/negotiations related to bids.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bid = models.ForeignKey(Bid, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bid_messages')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'bid_messages'
        ordering = ['created_at']
    
    def __str__(self):
        return f"Message on {self.bid} by {self.sender.get_full_name()}"
    
    def mark_as_read(self):
        """Mark message as read."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])


class BidReview(models.Model):
    """
    Reviews for bids (before acceptance).
    Task owners can review bid quality.
    """
    
    RATING_CHOICES = [
        (1, '1 - Poor'),
        (2, '2 - Fair'),
        (3, '3 - Good'),
        (4, '4 - Very Good'),
        (5, '5 - Excellent'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bid = models.OneToOneField(Bid, on_delete=models.CASCADE, related_name='review')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bid_reviews')
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'bid_reviews'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Review for {self.bid} - {self.rating}/5"


class BidNotification(models.Model):
    """
    Notifications related to bids.
    """
    
    NOTIFICATION_TYPES = [
        ('new_bid', 'New Bid Received'),
        ('bid_accepted', 'Bid Accepted'),
        ('bid_rejected', 'Bid Rejected'),
        ('counter_offer', 'Counter Offer Received'),
        ('bid_withdrawn', 'Bid Withdrawn'),
        ('bid_message', 'New Bid Message'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bid = models.ForeignKey(Bid, on_delete=models.CASCADE, related_name='notifications')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bid_notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'bid_notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
        ]
    
    def __str__(self):
        return f"{self.get_notification_type_display()} - {self.recipient.get_full_name()}"
    
    def mark_as_read(self):
        """Mark notification as read."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
