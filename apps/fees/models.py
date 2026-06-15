import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

DEFAULT_CURRENCY = getattr(settings, 'DEFAULT_CURRENCY', 'NPR')


class FeeRule(models.Model):
    """Admin-configurable fee rule (no hardcoded rates in application code)."""

    class FeeType(models.TextChoices):
        TASKER_COMMISSION = 'TASKER_COMMISSION', 'Tasker commission'
        CUSTOMER_SERVICE_FEE = 'CUSTOMER_SERVICE_FEE', 'Customer service fee'
        CANCELLATION_FEE = 'CANCELLATION_FEE', 'Cancellation fee'
        WITHDRAWAL_FEE = 'WITHDRAWAL_FEE', 'Withdrawal fee'
        TAX_FEE = 'TAX_FEE', 'Tax fee'
        BOOST_FEE = 'BOOST_FEE', 'Boost fee'
        FEATURED_TASK_FEE = 'FEATURED_TASK_FEE', 'Featured task fee'

        # Optional (kept for operational flexibility). Admin may use it for promotions.
        PROMOTIONAL_DISCOUNT = 'PROMOTIONAL_DISCOUNT', 'Promotional discount'

    class AppliesTo(models.TextChoices):
        CUSTOMER = 'CUSTOMER', 'Customer (poster)'
        TASKER = 'TASKER', 'Tasker'
        BOTH = 'BOTH', 'Both'

    class ValueType(models.TextChoices):
        PERCENTAGE = 'PERCENTAGE', 'Percentage of base amount'
        FIXED = 'FIXED', 'Fixed amount'

    class CancellationStage(models.TextChoices):
        BEFORE_ACCEPT = 'BEFORE_ACCEPT', 'Before bid accepted'
        AFTER_ACCEPT = 'AFTER_ACCEPT', 'After bid accepted'
        IN_PROGRESS = 'IN_PROGRESS', 'Task in progress'

    class ListingKind(models.TextChoices):
        TASK = 'task', 'Task (marketplace)'
        PROJECT = 'project', 'Project'
        SERVICE = 'service', 'Service'
        JOB = 'job', 'Job'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    fee_type = models.CharField(max_length=20, choices=FeeType.choices, db_index=True)
    applies_to = models.CharField(
        max_length=10,
        choices=AppliesTo.choices,
        default=AppliesTo.BOTH,
        help_text='Who this fee applies to (customer, tasker, or both).',
    )
    value_type = models.CharField(max_length=12, choices=ValueType.choices)
    value = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Percentage (e.g. 10 = 10%) or fixed NPR amount depending on value type.',
    )
    is_active = models.BooleanField(default=True, db_index=True)
    priority = models.PositiveIntegerField(
        default=100,
        help_text='Higher priority wins when multiple rules match the same fee type.',
    )
    min_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Rule applies only if transaction base amount is at least this.',
    )
    max_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Rule applies only if transaction base amount is at most this.',
    )
    category = models.ForeignKey(
        'tasks.Category',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fee_rules',
    )
    listing_kind = models.CharField(
        max_length=16,
        choices=ListingKind.choices,
        blank=True,
        default='',
        db_index=True,
        help_text='Apply only to this listing type (task, project, service, job). Blank = all types.',
    )
    user_tier = models.CharField(
        max_length=32,
        blank=True,
        help_text='Optional tier slug (e.g. bronze, silver). Blank = all tiers.',
    )
    cancellation_stage = models.CharField(
        max_length=20,
        choices=CancellationStage.choices,
        blank=True,
        help_text='Only used when fee_type is CANCELLATION.',
    )
    withdrawal_method = models.CharField(
        max_length=32,
        blank=True,
        help_text='esewa, khalti, bank_transfer, etc. Blank = all methods.',
    )
    currency = models.CharField(max_length=3, default=DEFAULT_CURRENCY)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fee_rules'
        ordering = ['-priority', 'fee_type', 'name']
        indexes = [
            models.Index(fields=['fee_type', 'is_active', '-priority']),
            models.Index(fields=['listing_kind', 'fee_type', 'is_active']),
            models.Index(fields=['cancellation_stage']),
            models.Index(fields=['withdrawal_method']),
        ]
        verbose_name = 'Fee rule'
        verbose_name_plural = 'Fee rules'

    def __str__(self):
        active = 'on' if self.is_active else 'off'
        if self.value_type == self.ValueType.PERCENTAGE:
            val = f'{self.value}%'
        else:
            val = f'{self.currency} {self.value}'
        return f'{self.name} ({self.fee_type} {val}, {active})'

    def is_currently_active(self, at: timezone.datetime | None = None) -> bool:
        """Evaluate active flag and start/end windows."""
        if not self.is_active:
            return False
        now = at or timezone.now()
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return True


class FeeTransaction(models.Model):
    """Audit log of every fee calculation applied in the system."""

    class Status(models.TextChoices):
        CALCULATED = 'calculated', 'Calculated (preview)'
        APPLIED = 'applied', 'Applied to transaction'
        REVERSED = 'reversed', 'Reversed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fee_transactions',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fee_transactions',
    )
    payment = models.ForeignKey(
        'payments.Payment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fee_transactions',
    )
    withdrawal_request = models.ForeignKey(
        'wallets.WithdrawalRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fee_transactions',
    )
    fee_type = models.CharField(max_length=20, db_index=True)
    payer = models.CharField(max_length=20, blank=True, help_text='Who paid this fee (CUSTOMER/TASKER/...).')
    receiver = models.CharField(max_length=20, blank=True, help_text='Who received this fee (PLATFORM/...).')
    base_amount = models.DecimalField(max_digits=12, decimal_places=2)
    fee_amount = models.DecimalField(max_digits=12, decimal_places=2)  # amount
    currency = models.CharField(max_length=3, default=DEFAULT_CURRENCY)
    rule_used = models.ForeignKey(
        FeeRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
    )
    rule_snapshot = models.JSONField(
        default=dict,
        blank=True,
        help_text='Copy of rule fields at calculation time for audit.',
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.CALCULATED,
        db_index=True,
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'fee_transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['fee_type', 'status', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]
        verbose_name = 'Fee transaction log'
        verbose_name_plural = 'Fee transaction logs'

    def __str__(self):
        return f'{self.fee_type} {self.fee_amount} {self.currency} ({self.status})'
