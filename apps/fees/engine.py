"""
Dynamic fee engine — all rates loaded from FeeRule rows in the database.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from django.conf import settings as django_settings
from django.core.exceptions import ValidationError
from django.db import transaction

from .cache import get_cached_active_rules
from .models import FeeRule, FeeTransaction

TWOPLACES = Decimal('0.01')
HUNDRED = Decimal('100')


def _q(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


@dataclass
class FeeContext:
    """Optional filters when resolving fee rules."""

    category_id: Optional[str] = None
    user_tier: str = ''
    cancellation_stage: str = ''
    withdrawal_method: str = ''
    payment_method: str = 'wallet'
    task_id: Optional[str] = None
    user_id: Optional[str] = None
    payment_id: Optional[str] = None
    currency: str = field(
        default_factory=lambda: getattr(django_settings, 'DEFAULT_CURRENCY', 'NPR')
    )


@dataclass
class FeeLineResult:
    fee_type: str
    amount: Decimal
    rule_id: Optional[str]
    rule_name: str
    value_type: str
    value: Decimal


class FeeEngine:
    """
    Resolves active FeeRule rows and computes monetary fees.

    Convention for task escrow / completion:
    - TASKER_COMMISSION: deducted from worker payout (base = task_amount)
    - CUSTOMER_SERVICE_FEE, TAX_FEE: added to customer total (base = task_amount)
    - PROMOTIONAL_DISCOUNT: reduces customer charges (stored as positive fee_amount, subtracted in totals)
    """

    @staticmethod
    def _match_rule(fee_type: str, base_amount: Decimal, ctx: FeeContext) -> Optional[FeeRule]:
        rules = get_cached_active_rules()
        base_amount = _q(base_amount)

        for rule in rules:
            if rule.fee_type != fee_type or not rule.is_currently_active():
                continue
            if rule.category_id:
                if not ctx.category_id or str(rule.category_id) != str(ctx.category_id):
                    continue
            if rule.user_tier and rule.user_tier != ctx.user_tier:
                continue
            if fee_type == FeeRule.FeeType.CANCELLATION_FEE:
                if rule.cancellation_stage and rule.cancellation_stage != ctx.cancellation_stage:
                    continue
            if fee_type == FeeRule.FeeType.WITHDRAWAL_FEE:
                if rule.withdrawal_method and rule.withdrawal_method != ctx.withdrawal_method:
                    continue
            if rule.min_amount is not None and base_amount < rule.min_amount:
                continue
            if rule.max_amount is not None and base_amount > rule.max_amount:
                continue
            return rule
        return None

    @staticmethod
    def _compute_fee_amount(rule: FeeRule, base_amount: Decimal) -> Decimal:
        base_amount = _q(base_amount)
        if rule.value_type == FeeRule.ValueType.PERCENTAGE:
            fee = base_amount * (rule.value / HUNDRED)
        else:
            fee = Decimal(str(rule.value))
        fee = _q(fee)
        return fee

    @staticmethod
    def _calculate_line(
        fee_type: str,
        base_amount: Decimal,
        ctx: FeeContext,
    ) -> FeeLineResult:
        base_amount = _q(base_amount)
        rule = FeeEngine._match_rule(fee_type, base_amount, ctx)
        if not rule:
            return FeeLineResult(
                fee_type=fee_type,
                amount=Decimal('0.00'),
                rule_id=None,
                rule_name='(no active rule)',
                value_type='',
                value=Decimal('0'),
            )
        amount = FeeEngine._compute_fee_amount(rule, base_amount)
        return FeeLineResult(
            fee_type=fee_type,
            amount=amount,
            rule_id=str(rule.id),
            rule_name=rule.name,
            value_type=rule.value_type,
            value=rule.value,
        )

    @staticmethod
    def calculate_commission(amount: Decimal, ctx: Optional[FeeContext] = None) -> FeeLineResult:
        return FeeEngine._calculate_line(
            FeeRule.FeeType.TASKER_COMMISSION,
            amount,
            ctx or FeeContext(),
        )

    @staticmethod
    def calculate_escrow(amount: Decimal, ctx: Optional[FeeContext] = None) -> FeeLineResult:
        return FeeEngine._calculate_line(
            FeeRule.FeeType.CUSTOMER_SERVICE_FEE,
            amount,
            ctx or FeeContext(),
        )

    @staticmethod
    def calculate_tax(amount: Decimal, ctx: Optional[FeeContext] = None) -> FeeLineResult:
        return FeeEngine._calculate_line(
            FeeRule.FeeType.TAX_FEE,
            amount,
            ctx or FeeContext(),
        )

    @staticmethod
    def calculate_cancellation(
        amount: Decimal,
        stage: str,
        ctx: Optional[FeeContext] = None,
    ) -> FeeLineResult:
        context = ctx or FeeContext()
        context.cancellation_stage = stage
        return FeeEngine._calculate_line(
            FeeRule.FeeType.CANCELLATION_FEE,
            amount,
            context,
        )

    @staticmethod
    def calculate_withdrawal(
        amount: Decimal,
        withdrawal_method: str = '',
        ctx: Optional[FeeContext] = None,
    ) -> FeeLineResult:
        context = ctx or FeeContext()
        context.withdrawal_method = withdrawal_method
        return FeeEngine._calculate_line(
            FeeRule.FeeType.WITHDRAWAL_FEE,
            amount,
            context,
        )

    @staticmethod
    def calculate_discount(amount: Decimal, ctx: Optional[FeeContext] = None) -> FeeLineResult:
        return FeeEngine._calculate_line(
            FeeRule.FeeType.PROMOTIONAL_DISCOUNT,
            amount,
            ctx or FeeContext(),
        )

    @staticmethod
    def calculate_task_settlement(
        task_amount: Decimal,
        ctx: Optional[FeeContext] = None,
        *,
        log: bool = False,
        status: str = FeeTransaction.Status.CALCULATED,
    ) -> dict[str, Any]:
        """
        Full marketplace breakdown for a task payment (bid / escrow).

        Returns keys aligned with API spec plus legacy payment-service fields.
        """
        task_amount = _q(task_amount)
        if task_amount <= 0:
            raise ValidationError('task_amount must be greater than 0')

        context = ctx or FeeContext()
        commission = FeeEngine.calculate_commission(task_amount, context)
        escrow = FeeEngine.calculate_escrow(task_amount, context)
        tax = FeeEngine.calculate_tax(task_amount, context)
        discount = FeeEngine.calculate_discount(task_amount, context)

        customer_extra = escrow.amount + tax.amount - discount.amount
        if customer_extra < 0:
            customer_extra = Decimal('0.00')

        total_customer_pays = _q(task_amount + customer_extra)
        worker_receives = _q(task_amount - commission.amount)
        if worker_receives < 0:
            worker_receives = Decimal('0.00')

        platform_profit = _q(commission.amount + escrow.amount + tax.amount - discount.amount)

        lines = {
            'commission': commission,
            'escrow': escrow,
            'tax': tax,
            'discount': discount,
        }

        tasker_commission_percent = Decimal('0')
        if commission.value_type == FeeRule.ValueType.PERCENTAGE:
            tasker_commission_percent = commission.value

        # Spec-aligned output keys + legacy keys for existing consumers.
        breakdown = {
            # Spec keys
            'task_amount': task_amount,
            'customer_service_fee': escrow.amount,
            'tasker_commission': commission.amount,
            'customer_total': total_customer_pays,
            'tasker_receive': worker_receives,
            'platform_profit': platform_profit,

            # Helpful extra fields
            'tax_fee': tax.amount,
            'promotional_discount': discount.amount,

            # Legacy keys (do not remove; frontend/backends may depend on these)
            'gross_amount': task_amount,
            'commission': commission.amount,
            'tasker_commission_percent': tasker_commission_percent,
            'escrow': escrow.amount,
            'tax': tax.amount,
            'discount': discount.amount,
            'total_customer_pays': total_customer_pays,
            'poster_total_held': total_customer_pays,
            'worker_receives': worker_receives,
            'net_amount': worker_receives,
            'platform_fee': commission.amount,
            'processing_fee': Decimal('0.00'),
            'total_fees': _q(commission.amount + escrow.amount + tax.amount),
            'currency': context.currency,
            'fees_enabled': any(line.amount > 0 for line in lines.values()),
            'lines': {
                key: {
                    'amount': str(line.amount),
                    'rule_id': line.rule_id,
                    'rule_name': line.rule_name,
                    'value_type': line.value_type,
                    'value': str(line.value),
                }
                for key, line in lines.items()
            },
        }

        if log:
            FeeEngine._log_lines(
                lines.values(),
                base_amount=task_amount,
                ctx=context,
                status=status,
            )

        return breakdown

    @staticmethod
    def calculate_total_fees(
        task_amount: Decimal,
        ctx: Optional[FeeContext] = None,
    ) -> dict[str, Decimal]:
        """Aggregate all fee-type amounts for a task base amount."""
        settlement = FeeEngine.calculate_task_settlement(task_amount, ctx)
        return {
            'commission': settlement['commission'],
            'escrow': settlement['escrow'],
            'tax': settlement['tax'],
            'discount': settlement['discount'],
            'total': _q(
                settlement['commission']
                + settlement['escrow']
                + settlement['tax']
            ),
        }

    @staticmethod
    @transaction.atomic
    def _log_lines(
        lines,
        *,
        base_amount: Decimal,
        ctx: FeeContext,
        status: str,
    ):
        from apps.tasks.models import Task
        from apps.users.models import User

        task = None
        user = None
        payment = None

        if ctx.task_id:
            task = Task.objects.filter(pk=ctx.task_id).first()
        if ctx.user_id:
            user = User.objects.filter(pk=ctx.user_id).first()
        if ctx.payment_id:
            from apps.payments.models import Payment
            payment = Payment.objects.filter(pk=ctx.payment_id).first()

        for line in lines:
            if line.amount <= 0 and not line.rule_id:
                continue
            rule = FeeRule.objects.filter(pk=line.rule_id).first() if line.rule_id else None
            FeeTransaction.objects.create(
                task=task,
                user=user or (task.owner if task else None),
                payment=payment,
                fee_type=line.fee_type,
                base_amount=base_amount,
                fee_amount=line.amount,
                currency=ctx.currency,
                rule_used=rule,
                rule_snapshot={
                    'rule_name': line.rule_name,
                    'value_type': line.value_type,
                    'value': str(line.value),
                },
                status=status,
            )

    @staticmethod
    def log_applied_task_fees(
        task_amount: Decimal,
        ctx: FeeContext,
        *,
        payment=None,
    ):
        """Persist fee audit rows when escrow is released / fees applied."""
        if payment:
            ctx.payment_id = str(payment.id)
        FeeEngine.calculate_task_settlement(
            task_amount,
            ctx,
            log=True,
            status=FeeTransaction.Status.APPLIED,
        )
