from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from decimal import Decimal
import uuid

DEFAULT_CURRENCY = getattr(settings, 'DEFAULT_CURRENCY', 'NPR')


class Wallet(models.Model):
    """
    User wallet for managing balances and transactions
    """
    
    CURRENCY_CHOICES = [
        ('NPR', 'Nepalese Rupee'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        'users.User',
        on_delete=models.CASCADE,
        related_name='wallet'
    )
    
    # Balance
    available_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Available balance for withdrawal'
    )
    pending_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Balance pending from incomplete tasks'
    )
    held_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Balance held in escrow'
    )
    total_earned = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Total amount earned (lifetime)'
    )
    total_withdrawn = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Total amount withdrawn (lifetime)'
    )
    
    # Currency
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default=DEFAULT_CURRENCY)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_frozen = models.BooleanField(default=False)
    frozen_reason = models.TextField(blank=True)
    frozen_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'wallets'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['is_active', 'is_frozen']),
        ]
    
    def __str__(self):
        return f"Wallet {self.user.email} - {self.available_balance} {self.currency}"
    
    @property
    def total_balance(self):
        """Total balance including pending and held"""
        return self.available_balance + self.pending_balance + self.held_balance
    
    def can_withdraw(self, amount):
        """Check if user can withdraw specified amount (accounts for other pending requests)."""
        from .services import WalletService

        return WalletService.can_withdraw_amount(self, amount)


class WalletTransaction(models.Model):
    """
    Detailed transaction log for wallet activities
    """
    
    TRANSACTION_TYPE_CHOICES = [
        ('credit', 'Credit'),
        ('debit', 'Debit'),
        ('hold', 'Hold'),
        ('release', 'Release'),
        ('refund', 'Refund'),
        ('fee', 'Fee'),
        ('bonus', 'Bonus'),
        ('penalty', 'Penalty'),
        ('adjustment', 'Adjustment'),
    ]
    
    TRANSACTION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('reversed', 'Reversed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    
    # Transaction details
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.CharField(max_length=3, default=DEFAULT_CURRENCY)
    status = models.CharField(max_length=20, choices=TRANSACTION_STATUS_CHOICES, default='pending')
    
    # Balance snapshots
    balance_before = models.DecimalField(max_digits=10, decimal_places=2)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Related object (payment, payout, task, etc.)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.UUIDField(null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')
    
    # Description
    description = models.TextField()
    notes = models.TextField(blank=True)
    
    # Reference
    reference_number = models.CharField(max_length=100, unique=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'wallet_transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet', 'created_at']),
            models.Index(fields=['transaction_type', 'status']),
            models.Index(fields=['reference_number']),
            models.Index(fields=['content_type', 'object_id']),
        ]
    
    def __str__(self):
        return f"{self.transaction_type} - {self.amount} {self.currency} ({self.status})"
    
    def save(self, *args, **kwargs):
        # Generate reference number if not provided
        if not self.reference_number:
            self.reference_number = f"TXN-{self.id}"
        super().save(*args, **kwargs)


class WithdrawalRequest(models.Model):
    """
    Withdrawal/payout requests from users
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
    ]
    
    METHOD_CHOICES = [
        ('bank_transfer', 'Bank Transfer'),
        ('esewa', 'eSewa'),
        ('khalti', 'Khalti'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='withdrawal_requests')
    
    # Amount
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('10.00'))]
    )
    currency = models.CharField(max_length=3, default=DEFAULT_CURRENCY)
    
    # Fees
    processing_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    net_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Amount after fees'
    )
    
    # Method
    withdrawal_method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    
    # Bank details (encrypted/masked)
    bank_account_name = models.CharField(max_length=200, blank=True)
    bank_account_number = models.CharField(max_length=100, blank=True)
    bank_name = models.CharField(max_length=200, blank=True)
    bank_routing_number = models.CharField(max_length=50, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Processing
    approved_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_withdrawals'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    rejection_reason = models.TextField(blank=True)
    failure_reason = models.TextField(blank=True)
    
    # Payment reference
    payment_reference = models.CharField(max_length=255, blank=True)
    
    # Metadata
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'withdrawal_requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"Withdrawal {self.id} - {self.amount} {self.currency} ({self.status})"
    
    def save(self, *args, **kwargs):
        # Calculate net amount
        if self.net_amount is None or self.net_amount == 0:
            self.net_amount = self.amount - self.processing_fee
        super().save(*args, **kwargs)


class WalletFreeze(models.Model):
    """
    Wallet freeze history for audit trail
    """
    
    FREEZE_REASON_CHOICES = [
        ('suspicious_activity', 'Suspicious Activity'),
        ('fraud_investigation', 'Fraud Investigation'),
        ('user_request', 'User Request'),
        ('compliance', 'Compliance Review'),
        ('dispute', 'Dispute'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='freeze_history')
    
    # Freeze details
    reason = models.CharField(max_length=50, choices=FREEZE_REASON_CHOICES)
    description = models.TextField()
    
    # Who froze/unfroze
    frozen_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='wallets_frozen'
    )
    unfrozen_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wallets_unfrozen'
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    frozen_at = models.DateTimeField(auto_now_add=True)
    unfrozen_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'wallet_freezes'
        ordering = ['-frozen_at']
        indexes = [
            models.Index(fields=['wallet', 'is_active']),
            models.Index(fields=['frozen_at']),
        ]
    
    def __str__(self):
        return f"Freeze {self.wallet.user.email} - {self.reason}"


class WalletLimit(models.Model):
    """
    Wallet transaction limits for security
    """
    
    LIMIT_TYPE_CHOICES = [
        ('daily_withdrawal', 'Daily Withdrawal'),
        ('weekly_withdrawal', 'Weekly Withdrawal'),
        ('monthly_withdrawal', 'Monthly Withdrawal'),
        ('single_transaction', 'Single Transaction'),
        ('daily_deposit', 'Daily Deposit'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='limits')
    
    # Limit details
    limit_type = models.CharField(max_length=30, choices=LIMIT_TYPE_CHOICES)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.CharField(max_length=3, default=DEFAULT_CURRENCY)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Metadata
    notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'wallet_limits'
        ordering = ['-created_at']
        unique_together = [['wallet', 'limit_type']]
        indexes = [
            models.Index(fields=['wallet', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.wallet.user.email} - {self.limit_type}: {self.amount} {self.currency}"
