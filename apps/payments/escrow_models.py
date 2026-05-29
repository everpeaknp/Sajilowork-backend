"""
Escrow models for holding payments until task completion.
"""
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models

DEFAULT_CURRENCY = getattr(settings, 'DEFAULT_CURRENCY', 'NPR')
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class Escrow(models.Model):
    """
    Escrow for holding payments until task completion.
    Created when a bid is accepted and payment is made.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('held', 'Held'),
        ('released', 'Released'),
        ('refunded', 'Refunded'),
        ('disputed', 'Disputed'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Primary fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.OneToOneField(
        'payments.Payment',
        on_delete=models.PROTECT,
        related_name='escrow'
    )
    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.PROTECT,
        related_name='escrows'
    )
    bid = models.ForeignKey(
        'bids.Bid',
        on_delete=models.PROTECT,
        related_name='escrows'
    )
    
    # Parties
    payer = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='escrows_as_payer',
        help_text='Task owner who pays'
    )
    payee = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='escrows_as_payee',
        help_text='Tasker who receives payment'
    )
    
    # Amounts
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Total escrow amount'
    )
    currency = models.CharField(max_length=3, default=DEFAULT_CURRENCY)
    
    # Fee breakdown
    platform_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Platform service fee'
    )
    payment_processing_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Payment processor fee'
    )
    net_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Amount payee will receive after fees'
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    held_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    
    # Auto-release settings
    auto_release_enabled = models.BooleanField(
        default=True,
        help_text='Automatically release after completion approval'
    )
    auto_release_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Scheduled auto-release date'
    )
    auto_release_days = models.PositiveIntegerField(
        default=7,
        help_text='Days after completion to auto-release'
    )
    
    # Dispute
    is_disputed = models.BooleanField(default=False)
    dispute_reason = models.TextField(blank=True)
    dispute_raised_at = models.DateTimeField(null=True, blank=True)
    dispute_resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Release details
    release_reason = models.TextField(blank=True)
    released_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='released_escrows'
    )
    
    # Refund details
    refund_reason = models.TextField(blank=True)
    refunded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refunded_escrows'
    )
    
    # Metadata
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'escrows'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['payer', 'status']),
            models.Index(fields=['payee', 'status']),
            models.Index(fields=['task']),
            models.Index(fields=['auto_release_at']),
        ]
    
    def __str__(self):
        return f"Escrow {self.id} - {self.amount} {self.currency} ({self.status})"
    
    def save(self, *args, **kwargs):
        # Calculate net amount if not set
        if self.net_amount is None:
            self.net_amount = self.amount - self.platform_fee - self.payment_processing_fee
        super().save(*args, **kwargs)
    
    def hold(self):
        """Mark escrow as held (payment received)."""
        if self.status != 'pending':
            raise ValueError(f"Cannot hold escrow with status: {self.status}")
        
        self.status = 'held'
        self.held_at = timezone.now()
        
        # Set auto-release date
        if self.auto_release_enabled:
            from datetime import timedelta
            self.auto_release_at = timezone.now() + timedelta(days=self.auto_release_days)
        
        self.save(update_fields=['status', 'held_at', 'auto_release_at'])
    
    def release(self, released_by: User, reason: str = ''):
        """Release escrow to payee."""
        if self.status not in ['held', 'disputed']:
            raise ValueError(f"Cannot release escrow with status: {self.status}")
        
        if self.is_disputed:
            raise ValueError("Cannot release disputed escrow without resolution")
        
        self.status = 'released'
        self.released_at = timezone.now()
        self.released_by = released_by
        self.release_reason = reason
        self.save(update_fields=[
            'status', 'released_at', 'released_by', 'release_reason'
        ])
        
        # TODO: Trigger payout to payee
        # payout_service.create_payout(self)
    
    def refund(self, refunded_by: User, reason: str = ''):
        """Refund escrow to payer."""
        if self.status not in ['held', 'disputed']:
            raise ValueError(f"Cannot refund escrow with status: {self.status}")
        
        self.status = 'refunded'
        self.refunded_at = timezone.now()
        self.refunded_by = refunded_by
        self.refund_reason = reason
        self.save(update_fields=[
            'status', 'refunded_at', 'refunded_by', 'refund_reason'
        ])
        
        # TODO: Trigger refund to payer
        # refund_service.create_refund(self)
    
    def raise_dispute(self, reason: str):
        """Raise a dispute on the escrow."""
        if self.status != 'held':
            raise ValueError(f"Cannot dispute escrow with status: {self.status}")
        
        self.is_disputed = True
        self.status = 'disputed'
        self.dispute_reason = reason
        self.dispute_raised_at = timezone.now()
        self.save(update_fields=[
            'is_disputed', 'status', 'dispute_reason', 'dispute_raised_at'
        ])
    
    def resolve_dispute(self, resolution: str):
        """Resolve a dispute."""
        if not self.is_disputed:
            raise ValueError("No active dispute to resolve")
        
        self.is_disputed = False
        self.status = 'held'  # Back to held, awaiting release/refund decision
        self.dispute_resolved_at = timezone.now()
        self.notes = f"{self.notes}\n\nDispute Resolution: {resolution}"
        self.save(update_fields=[
            'is_disputed', 'status', 'dispute_resolved_at', 'notes'
        ])
    
    @property
    def is_held(self):
        """Check if escrow is currently held."""
        return self.status == 'held'
    
    @property
    def is_released(self):
        """Check if escrow is released."""
        return self.status == 'released'
    
    @property
    def is_refunded(self):
        """Check if escrow is refunded."""
        return self.status == 'refunded'
    
    @property
    def can_auto_release(self):
        """Check if escrow can be auto-released."""
        return (
            self.auto_release_enabled and
            self.status == 'held' and
            not self.is_disputed and
            self.auto_release_at and
            timezone.now() >= self.auto_release_at
        )
    
    @property
    def days_until_auto_release(self):
        """Calculate days until auto-release."""
        if self.auto_release_at and self.status == 'held':
            delta = self.auto_release_at - timezone.now()
            return max(0, delta.days)
        return None


class EscrowTransaction(models.Model):
    """
    Track all transactions related to an escrow.
    """
    
    TRANSACTION_TYPES = [
        ('hold', 'Hold'),
        ('release', 'Release'),
        ('refund', 'Refund'),
        ('dispute_raised', 'Dispute Raised'),
        ('dispute_resolved', 'Dispute Resolved'),
        ('fee_deducted', 'Fee Deducted'),
        ('adjustment', 'Adjustment'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    escrow = models.ForeignKey(
        Escrow,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    
    # Transaction details
    transaction_type = models.CharField(max_length=30, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default=DEFAULT_CURRENCY)
    description = models.TextField()
    
    # Actor
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'escrow_transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['escrow', '-created_at']),
            models.Index(fields=['transaction_type', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.amount} {self.currency}"


class EscrowDispute(models.Model):
    """
    Detailed dispute information for escrows.
    """
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('under_review', 'Under Review'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    RESOLUTION_CHOICES = [
        ('release_to_payee', 'Release to Payee'),
        ('refund_to_payer', 'Refund to Payer'),
        ('partial_release', 'Partial Release'),
        ('no_action', 'No Action'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    escrow = models.ForeignKey(
        Escrow,
        on_delete=models.CASCADE,
        related_name='disputes'
    )
    
    # Dispute details
    raised_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='raised_escrow_disputes'
    )
    against = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='escrow_disputes_against'
    )
    reason = models.TextField()
    evidence = models.JSONField(default=list, blank=True, help_text="List of evidence files")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    
    # Resolution
    resolution_type = models.CharField(
        max_length=30,
        choices=RESOLUTION_CHOICES,
        blank=True
    )
    resolution_notes = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_escrow_disputes'
    )
    
    # Partial release amounts (if applicable)
    partial_release_to_payee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    partial_refund_to_payer = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'escrow_disputes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['escrow', 'status']),
            models.Index(fields=['status', '-created_at']),
        ]
    
    def __str__(self):
        return f"Dispute on {self.escrow} - {self.status}"
    
    def mark_under_review(self, reviewer: User):
        """Mark dispute as under review."""
        if self.status != 'open':
            raise ValueError("Can only review open disputes")
        
        self.status = 'under_review'
        self.reviewed_at = timezone.now()
        self.resolved_by = reviewer
        self.save(update_fields=['status', 'reviewed_at', 'resolved_by'])
    
    def resolve(self, resolution_type: str, notes: str, resolved_by: User):
        """Resolve the dispute."""
        if self.status not in ['open', 'under_review']:
            raise ValueError(f"Cannot resolve dispute with status: {self.status}")
        
        self.status = 'resolved'
        self.resolution_type = resolution_type
        self.resolution_notes = notes
        self.resolved_by = resolved_by
        self.resolved_at = timezone.now()
        self.save(update_fields=[
            'status', 'resolution_type', 'resolution_notes',
            'resolved_by', 'resolved_at'
        ])
        
        # Update escrow based on resolution
        if resolution_type == 'release_to_payee':
            self.escrow.resolve_dispute(notes)
            self.escrow.release(resolved_by, f"Dispute resolved: {notes}")
        elif resolution_type == 'refund_to_payer':
            self.escrow.resolve_dispute(notes)
            self.escrow.refund(resolved_by, f"Dispute resolved: {notes}")
        elif resolution_type == 'partial_release':
            self.escrow.resolve_dispute(notes)
            # TODO: Implement partial release logic
        else:  # no_action
            self.escrow.resolve_dispute(notes)
