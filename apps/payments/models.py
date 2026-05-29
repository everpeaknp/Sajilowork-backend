from django.conf import settings
from django.db import models

from .escrow_constants import (
    ESCROW_STATUS_CHOICES,
    PAYMENT_TX_STATUS_CHOICES,
    PENDING_PAYMENT,
    PAYMENT_TX_PENDING,
)
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid

DEFAULT_CURRENCY = getattr(settings, 'DEFAULT_CURRENCY', 'NPR')


class Payment(models.Model):
    """
    Main payment model for tracking all payments in the system.
    Supports wallet escrow and local payment methods (eSewa, Khalti, bank).
    """
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
        ('partially_refunded', 'Partially Refunded'),
        ('disputed', 'Disputed'),
        ('held', 'Held in Escrow'),
        ('released', 'Released from Escrow'),
    ]
    
    PAYMENT_TYPE_CHOICES = [
        ('task_payment', 'Task Payment'),
        ('service_fee', 'Service Fee'),
        ('refund', 'Refund'),
        ('payout', 'Payout'),
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('wallet', 'Wallet Balance'),
        ('esewa', 'eSewa'),
        ('khalti', 'Khalti'),
        ('bank_account', 'Bank Account'),
        ('bank_transfer', 'Bank Transfer'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # User relationships
    payer = models.ForeignKey(
        'users.User',
        on_delete=models.PROTECT,
        related_name='payments_made',
        help_text='User making the payment'
    )
    payee = models.ForeignKey(
        'users.User',
        on_delete=models.PROTECT,
        related_name='payments_received',
        help_text='User receiving the payment',
        null=True,
        blank=True
    )
    
    # Related object (task, bid, etc.)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    related_object = GenericForeignKey('content_type', 'object_id')
    
    # Payment details
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Payment amount'
    )
    currency = models.CharField(max_length=3, default=DEFAULT_CURRENCY)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
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
        help_text='Amount after fees',
        null=True,
        blank=True
    )
    
    # Escrow
    is_escrowed = models.BooleanField(default=False)
    escrow_released_at = models.DateTimeField(null=True, blank=True)
    escrow_release_scheduled_at = models.DateTimeField(null=True, blank=True)
    
    # Refund
    refund_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    refund_reason = models.TextField(blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    failure_reason = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['payer', 'status']),
            models.Index(fields=['payee', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['content_type', 'object_id']),
        ]
    
    def __str__(self):
        return f"Payment {self.id} - {self.amount} {self.currency} ({self.status})"
    
    def save(self, *args, **kwargs):
        # Calculate net amount
        if self.net_amount is None:
            self.net_amount = self.amount - self.platform_fee - self.payment_processing_fee
        super().save(*args, **kwargs)


class PaymentMethod(models.Model):
    """
    Stored payment methods for users (cards, bank accounts, eSewa, etc.)
    """
    
    METHOD_TYPE_CHOICES = [
        ('bank_account', 'Bank Account'),
        ('esewa', 'eSewa'),
        ('khalti', 'Khalti'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='payment_methods')
    
    # Method details
    method_type = models.CharField(max_length=20, choices=METHOD_TYPE_CHOICES)
    is_default = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    
    # Card details (masked, legacy records)
    card_brand = models.CharField(max_length=50, blank=True)
    card_last4 = models.CharField(max_length=4, blank=True)
    card_exp_month = models.IntegerField(null=True, blank=True)
    card_exp_year = models.IntegerField(null=True, blank=True)
    
    # Bank account details (masked)
    bank_name = models.CharField(max_length=100, blank=True)
    account_last4 = models.CharField(max_length=4, blank=True)
    
    # eSewa account details
    esewa_account_name = models.CharField(max_length=255, blank=True, help_text='Full name on eSewa account')
    esewa_phone_number = models.CharField(max_length=15, blank=True, help_text='eSewa phone number (10 digits)')
    
    # Metadata
    billing_details = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'payment_methods'
        ordering = ['-is_default', '-created_at']
        indexes = [
            models.Index(fields=['user', 'is_default']),
        ]
    
    def __str__(self):
        if self.method_type == 'card':
            return f"{self.card_brand} ****{self.card_last4}"
        elif self.method_type == 'bank_account':
            return f"{self.bank_name} ****{self.account_last4}"
        elif self.method_type == 'esewa':
            # Mask phone number: 98068****02
            if self.esewa_phone_number and len(self.esewa_phone_number) >= 4:
                masked = self.esewa_phone_number[:5] + '****' + self.esewa_phone_number[-2:]
                return f"eSewa - {masked}"
            return f"eSewa - {self.esewa_account_name}"
        return f"{self.method_type} - {self.id}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default payment method per user
        if self.is_default:
            PaymentMethod.objects.filter(user=self.user, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)


class Refund(models.Model):
    """
    Refund tracking for payments
    """
    
    REFUND_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    REFUND_REASON_CHOICES = [
        ('duplicate', 'Duplicate Payment'),
        ('fraudulent', 'Fraudulent'),
        ('requested_by_customer', 'Requested by Customer'),
        ('task_cancelled', 'Task Cancelled'),
        ('task_not_completed', 'Task Not Completed'),
        ('dispute', 'Dispute'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='refunds')
    
    # Refund details
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.CharField(max_length=3, default=DEFAULT_CURRENCY)
    reason = models.CharField(max_length=50, choices=REFUND_REASON_CHOICES)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=REFUND_STATUS_CHOICES, default='pending')
    
    # Metadata
    initiated_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    failure_reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'refunds'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['payment', 'status']),
        ]
    
    def __str__(self):
        return f"Refund {self.id} - {self.amount} {self.currency} ({self.status})"


class Payout(models.Model):
    """
    Payout tracking for taskers withdrawing their earnings
    """
    
    PAYOUT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYOUT_METHOD_CHOICES = [
        ('bank_transfer', 'Bank Transfer'),
        ('esewa', 'eSewa'),
        ('khalti', 'Khalti'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('users.User', on_delete=models.PROTECT, related_name='payouts')
    
    # Payout details
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.CharField(max_length=3, default=DEFAULT_CURRENCY)
    payout_method = models.CharField(max_length=20, choices=PAYOUT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=PAYOUT_STATUS_CHOICES, default='pending')
    
    # Bank details (encrypted/masked)
    bank_account_id = models.UUIDField(null=True, blank=True)
    
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
    
    # Metadata
    description = models.TextField(blank=True)
    failure_reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'payouts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"Payout {self.id} - {self.amount} {self.currency} ({self.status})"


class Transaction(models.Model):
    """
    Transaction log for all financial activities
    """
    
    TRANSACTION_TYPE_CHOICES = [
        ('payment', 'Payment'),
        ('refund', 'Refund'),
        ('payout', 'Payout'),
        ('fee', 'Fee'),
        ('adjustment', 'Adjustment'),
        ('bonus', 'Bonus'),
        ('penalty', 'Penalty'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('users.User', on_delete=models.PROTECT, related_name='transactions')
    
    # Transaction details
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default=DEFAULT_CURRENCY)
    balance_before = models.DecimalField(max_digits=10, decimal_places=2)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Related objects
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True)
    refund = models.ForeignKey(Refund, on_delete=models.SET_NULL, null=True, blank=True)
    payout = models.ForeignKey(Payout, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Metadata
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['transaction_type', 'created_at']),
        ]
    
    def __str__(self):
        return f"Transaction {self.id} - {self.transaction_type} - {self.amount} {self.currency}"


# Wallet models moved to wallets app to avoid conflicts
# Import from wallets app if needed:
# from apps.wallets.models import Wallet, WalletTransaction


class Escrow(models.Model):
    """
    Escrow account per task — authoritative lifecycle state for marketplace funds.
    API alias: EscrowAccount.
    """

    STATUS_CHOICES = ESCROW_STATUS_CHOICES

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.OneToOneField(
        Payment,
        on_delete=models.CASCADE,
        related_name='escrow_account',
    )
    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.CASCADE,
        related_name='escrows',
    )
    bid = models.ForeignKey(
        'bids.Bid',
        on_delete=models.CASCADE,
        related_name='escrows',
    )
    payer = models.ForeignKey(
        'users.User',
        on_delete=models.PROTECT,
        related_name='escrows_funded',
    )
    payee = models.ForeignKey(
        'users.User',
        on_delete=models.PROTECT,
        related_name='escrows_as_tasker',
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    platform_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    processing_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    net_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Amount tasker receives after fees on release',
    )
    currency = models.CharField(max_length=3, default=DEFAULT_CURRENCY)

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=PENDING_PAYMENT,
    )
    funding_method = models.CharField(max_length=20, default='wallet')
    idempotency_key = models.CharField(max_length=128, blank=True, db_index=True)

    locked_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    auto_release_at = models.DateTimeField(null=True, blank=True)

    release_reason = models.TextField(blank=True)
    refund_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'escrows'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['task'], name='unique_escrow_per_task'),
        ]
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['task']),
            models.Index(fields=['bid']),
            models.Index(fields=['payer', 'status']),
        ]

    def __str__(self):
        return f'Escrow {self.id} — {self.task_id} ({self.status})'


class PaymentTransaction(models.Model):
    """Gateway payment attempts (eSewa/Khalti) with idempotency and audit trail."""

    STATUS_CHOICES = PAYMENT_TX_STATUS_CHOICES

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    escrow = models.ForeignKey(
        Escrow,
        on_delete=models.CASCADE,
        related_name='gateway_transactions',
        null=True,
        blank=True,
    )
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='gateway_transactions',
        null=True,
        blank=True,
    )
    payer = models.ForeignKey(
        'users.User',
        on_delete=models.PROTECT,
        related_name='payment_transactions',
    )

    provider = models.CharField(max_length=20)
    transaction_id = models.CharField(max_length=128, db_index=True)
    idempotency_key = models.CharField(max_length=128, unique=True)
    provider_reference = models.CharField(max_length=255, blank=True)

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default=DEFAULT_CURRENCY)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PAYMENT_TX_PENDING)

    failure_reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'payment_transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['provider', 'status']),
            models.Index(fields=['transaction_id']),
        ]

    def __str__(self):
        return f'{self.provider} {self.transaction_id} ({self.status})'


class EscrowAuditLog(models.Model):
    """Immutable audit trail for every escrow state transition."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    escrow = models.ForeignKey(Escrow, on_delete=models.CASCADE, related_name='audit_logs')
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30)
    actor = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    note = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'escrow_audit_logs'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['escrow', 'created_at']),
        ]

    def __str__(self):
        return f'{self.escrow_id}: {self.from_status} -> {self.to_status}'


class PlatformFeeSettings(models.Model):
    """
    Singleton platform fee configuration (admin-controlled).

    Task poster pays the bid amount into escrow. On task completion, the tasker
    receives the bid amount minus the platform commission (and optional processing fees).
    """

    singleton_id = models.PositiveSmallIntegerField(
        primary_key=True,
        default=1,
        editable=False,
    )
    is_enabled = models.BooleanField(
        default=True,
        help_text='When disabled, no platform fee is deducted on task completion.',
    )
    tasker_commission_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Percentage deducted from the task payment when crediting the tasker (e.g. 10 = 10%).',
    )
    poster_service_fee_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Optional extra % charged to the poster on top of the bid (usually 0).',
    )
    min_platform_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Minimum platform fee per task (NPR). 0 = no minimum.',
    )
    max_platform_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Maximum platform fee per task (NPR). Leave empty for no cap.',
    )
    apply_processing_fee_on_wallet = models.BooleanField(
        default=False,
        help_text='Apply card-style processing fees for wallet escrow payments (usually off for NPR).',
    )
    wallet_processing_fee_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    wallet_processing_fee_fixed = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    card_processing_fee_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('2.90'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    card_processing_fee_fixed = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    admin_notes = models.TextField(
        blank=True,
        help_text='Internal notes for admins (not shown to users).',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'platform_fee_settings'
        verbose_name = 'Platform fee settings'
        verbose_name_plural = 'Platform fee settings'

    def __str__(self):
        return (
            f'Platform fees — tasker {self.tasker_commission_percent}% '
            f'({"on" if self.is_enabled else "off"})'
        )

    def save(self, *args, **kwargs):
        self.singleton_id = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
