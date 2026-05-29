import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from .events import RuleEvent

User = settings.AUTH_USER_MODEL


class RuleCategory(models.TextChoices):
    ESCROW = 'ESCROW', 'Escrow'
    OFFER = 'OFFER', 'Offer / bidding'
    ASSIGNMENT = 'ASSIGNMENT', 'Task assignment'
    REVIEW = 'REVIEW', 'Reviews'
    CANCELLATION = 'CANCELLATION', 'Cancellation'
    DISPUTE = 'DISPUTE', 'Dispute'
    WALLET = 'WALLET', 'Wallet'
    TRUST = 'TRUST', 'Trust & ranking'
    VERIFICATION = 'VERIFICATION', 'Verification'
    FRAUD = 'FRAUD', 'Fraud prevention'
    MESSAGING = 'MESSAGING', 'Messaging'
    AUTO_RELEASE = 'AUTO_RELEASE', 'Auto-release'
    REFUND = 'REFUND', 'Refund'
    PROMOTION = 'PROMOTION', 'Promotion'
    TASK_EXPIRY = 'TASK_EXPIRY', 'Task expiry'
    PAYMENT_BYPASS = 'PAYMENT_BYPASS', 'Payment bypass prevention'
    WITHDRAWAL = 'WITHDRAWAL', 'Withdrawal'
    NOTIFICATION = 'NOTIFICATION', 'Notification'
    MODERATION = 'MODERATION', 'Account moderation'


class EnforcementMode(models.TextChoices):
    BLOCK = 'BLOCK', 'Block action'
    WARN = 'WARN', 'Warn only'
    AUTO = 'AUTO', 'Automatic side effect'
    NOTIFY = 'NOTIFY', 'Send notification'


class RulePolicy(models.Model):
    """
    Admin-configurable marketplace policy.
    Parameters are JSON — validated by category handlers at runtime.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(max_length=32, choices=RuleCategory.choices, db_index=True)
    slug = models.SlugField(max_length=80, help_text='Unique key within category, e.g. require_escrow_before_start')
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    priority = models.PositiveIntegerField(
        default=100,
        help_text='Higher runs first; first blocking violation stops evaluation when stop_on_block=True globally.',
    )
    enforcement = models.CharField(
        max_length=10,
        choices=EnforcementMode.choices,
        default=EnforcementMode.BLOCK,
    )
    event_triggers = models.JSONField(
        default=list,
        blank=True,
        help_text='List of RuleEvent values, e.g. ["task.cancelled", "bid.created"]. Empty = category default.',
    )
    conditions = models.JSONField(
        default=dict,
        blank=True,
        help_text='Optional filters: roles, statuses, min_amount, verified_only, etc.',
    )
    parameters = models.JSONField(
        default=dict,
        blank=True,
        help_text='Category-specific thresholds and toggles.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'rule_policies'
        ordering = ['category', '-priority', 'slug']
        verbose_name = 'Rule policy'
        verbose_name_plural = 'Rule policies'
        constraints = [
            models.UniqueConstraint(fields=['category', 'slug'], name='uniq_rule_policy_category_slug'),
        ]
        indexes = [
            models.Index(fields=['category', 'is_active']),
        ]

    def __str__(self):
        return f'{self.category}:{self.slug}'


class RuleEvaluationLog(models.Model):
    """Audit trail for rule engine runs."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.CharField(max_length=64, db_index=True)
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rule_evaluations',
    )
    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rule_evaluations',
    )
    allowed = models.BooleanField()
    policies_evaluated = models.PositiveIntegerField(default=0)
    violations = models.JSONField(default=list, blank=True)
    actions = models.JSONField(default=list, blank=True)
    context_snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'rule_evaluation_logs'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.event} allowed={self.allowed}'


# Legacy moderation model (kept for backward compatibility with existing admin/API)
class PlatformRule(models.Model):
    """Admin-configurable platform moderation and policy rules."""

    class RuleType(models.TextChoices):
        AUTO_SUSPEND_EXCESS_CANCELLATIONS = (
            'AUTO_SUSPEND_EXCESS_CANCELLATIONS',
            'Auto-suspend after excess task cancellations',
        )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule_type = models.CharField(max_length=64, choices=RuleType.choices, unique=True, db_index=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    max_cancellations = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(1)],
    )
    suspension_hours = models.PositiveIntegerField(
        default=24,
        validators=[MinValueValidator(1)],
    )
    counting_window_days = models.PositiveIntegerField(null=True, blank=True)
    applies_to_customers = models.BooleanField(default=True)
    applies_to_taskers = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'platform_rules'
        ordering = ['rule_type']
        verbose_name = 'Platform rule (legacy)'
        verbose_name_plural = 'Platform rules (legacy)'

    def __str__(self):
        status = 'active' if self.is_active else 'inactive'
        return f'{self.name} ({status})'


class AccountSuspensionLog(models.Model):
    """Audit log when a user is auto-suspended for rule violations."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='suspension_logs')
    rule = models.ForeignKey(
        PlatformRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='suspension_logs',
    )
    policy = models.ForeignKey(
        RulePolicy,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='suspension_logs',
    )
    cancellation_count = models.PositiveIntegerField()
    suspended_until = models.DateTimeField()
    reason = models.TextField()
    lifted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'account_suspension_logs'
        ordering = ['-created_at']

    def __str__(self):
        return f'Suspension {self.user_id} until {self.suspended_until}'
