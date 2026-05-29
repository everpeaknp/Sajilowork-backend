"""
Bridge to the dynamic FeeEngine (apps.fees).

All fee percentages and amounts are loaded from FeeRule rows in the database.
"""
from decimal import Decimal

from django.conf import settings as django_settings
from django.core.exceptions import ValidationError

from apps.fees.engine import FeeContext, FeeEngine


class PlatformFeeService:
    """Backward-compatible facade over FeeEngine for payments / escrow."""

    @staticmethod
    def calculate_task_payment_fees(
        amount,
        *,
        payment_method: str = 'wallet',
        category_id=None,
        user_tier: str = '',
    ) -> dict:
        ctx = FeeContext(
            payment_method=payment_method,
            category_id=str(category_id) if category_id else None,
            user_tier=user_tier or '',
        )
        return FeeEngine.calculate_task_settlement(Decimal(str(amount)), ctx)

    @staticmethod
    def apply_fees_to_payment(payment, *, persist: bool = True) -> dict:
        ctx = FeeContext(
            payment_method=payment.payment_method or 'wallet',
            payment_id=str(payment.id),
            task_id=str(payment.object_id) if payment.object_id else None,
            user_id=str(payment.payee_id) if payment.payee_id else None,
        )
        breakdown = FeeEngine.calculate_task_settlement(payment.amount, ctx)
        payment.platform_fee = breakdown['platform_fee']
        payment.payment_processing_fee = breakdown.get('processing_fee', Decimal('0'))
        payment.net_amount = breakdown['net_amount']
        metadata = dict(payment.metadata or {})
        metadata['fee_breakdown'] = {k: str(v) for k, v in breakdown.items() if k != 'lines'}
        metadata['fee_lines'] = breakdown.get('lines', {})
        payment.metadata = metadata
        if persist:
            payment.save(
                update_fields=[
                    'platform_fee',
                    'payment_processing_fee',
                    'net_amount',
                    'metadata',
                ]
            )
        FeeEngine.log_applied_task_fees(payment.amount, ctx, payment=payment)
        return breakdown

    @staticmethod
    def public_settings_payload() -> dict:
        from apps.fees.models import FeeRule

        commission = FeeRule.objects.filter(
            fee_type=FeeRule.FeeType.COMMISSION,
            is_active=True,
        ).order_by('-priority').first()
        return {
            'is_enabled': commission is not None,
            'tasker_commission_percent': str(commission.value) if commission else '0',
            'poster_service_fee_percent': '0',
            'min_platform_fee': '0',
            'max_platform_fee': None,
            'currency': getattr(django_settings, 'DEFAULT_CURRENCY', 'NPR'),
            'source': 'fee_rules',
        }
