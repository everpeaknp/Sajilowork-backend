"""
Platform-wide business metrics for the admin analytics dashboard.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from apps.dashboard.services import DashboardService
from apps.disputes.models import Dispute
from apps.fees.models import FeeTransaction
from apps.payments.escrow_constants import (
    COMPLETED,
    DISPUTED,
    FUNDED,
    IN_PROGRESS,
    PENDING_PAYMENT,
    SUBMITTED,
)
from apps.payments.models import Escrow, Payment, Refund
from apps.tasks.models import Task
from apps.wallets.models import Wallet, WalletTransaction, WithdrawalRequest

DEFAULT_CURRENCY = getattr(settings, 'DEFAULT_CURRENCY', 'NPR')

WALLET_RECHARGE_Q = (
    Q(metadata__channel='admin_manual')
    | Q(metadata__gateway='esewa')
    | Q(metadata__esewa_transaction_uuid__isnull=False)
    | Q(description__icontains='wallet recharge')
    | Q(description__icontains='manual wallet recharge')
)


def _dec(value) -> Decimal:
    if value is None:
        return Decimal('0.00')
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _f(value) -> float:
    return float(_dec(value))


def _period_start(days: int | None):
    if days is None or days <= 0:
        return None
    return timezone.now() - timedelta(days=days)


class BusinessMetricsService:
    """Aggregate financial and operational KPIs for admin reporting."""

    @staticmethod
    def _build_charts(
        *,
        daily_fees,
        daily_tasks,
        fees_by_type,
        payments_by_status,
        escrow_by_status,
        withdrawals_by_status,
        growth,
        recharges_total,
        withdrawals_total,
        net_fees,
        refunds_total,
        tasker_payouts,
        gmv,
    ) -> dict:
        """Serialize metrics for Chart.js on the admin dashboard."""

        def _fmt_day(day):
            if not day:
                return ''
            return day.strftime('%d %b')

        fee_labels = [_fmt_day(r['day']) for r in daily_fees]
        fee_values = [_f(r['total']) for r in daily_fees]

        task_labels = [_fmt_day(r['day']) for r in daily_tasks]
        task_values = [int(r['count'] or 0) for r in daily_tasks]

        fee_type_labels = [
            (r['fee_type'] or 'other').replace('_', ' ').title() for r in fees_by_type
        ]
        fee_type_values = [_f(r['total']) for r in fees_by_type]

        payment_labels = [(r['status'] or 'unknown').replace('_', ' ').title() for r in payments_by_status]
        payment_values = [_f(r['total']) for r in payments_by_status]

        escrow_labels = [(r['status'] or 'unknown').replace('_', ' ').title() for r in escrow_by_status]
        escrow_values = [_f(r['total']) for r in escrow_by_status]

        withdrawal_labels = [
            (r['status'] or 'unknown').replace('_', ' ').title() for r in withdrawals_by_status
        ]
        withdrawal_values = [_f(r['total']) for r in withdrawals_by_status]

        return {
            'fee_trend': {'labels': fee_labels, 'values': fee_values},
            'task_trend': {'labels': task_labels, 'values': task_values},
            'fees_by_type': {'labels': fee_type_labels, 'values': fee_type_values},
            'payments_by_status': {'labels': payment_labels, 'values': payment_values},
            'escrow_by_status': {'labels': escrow_labels, 'values': escrow_values},
            'withdrawals_by_status': {'labels': withdrawal_labels, 'values': withdrawal_values},
            'cash_flow': {
                'labels': ['Recharges', 'Withdrawals', 'Platform fees', 'Refunds', 'Paid to taskers', 'Task GMV'],
                'values': [
                    recharges_total,
                    withdrawals_total,
                    net_fees,
                    refunds_total,
                    tasker_payouts,
                    gmv,
                ],
            },
            'growth': {
                'labels': ['New users', 'New tasks', 'New bids'],
                'values': [
                    int(growth.get('new_users') or 0),
                    int(growth.get('new_tasks') or 0),
                    int(growth.get('new_bids') or 0),
                ],
            },
        }

    @staticmethod
    def get_dashboard(*, period_days: int | None = 30) -> dict:
        start = _period_start(period_days)
        period_label = 'All time' if start is None else f'Last {period_days} days'

        def _filter_qs(qs, field='created_at'):
            if start is None:
                return qs
            return qs.filter(**{f'{field}__gte': start})

        # —— Wallet recharges (top-ups) ——
        recharge_txs = WalletTransaction.objects.filter(
            status='completed',
            transaction_type__in=('credit', 'bonus'),
        ).filter(WALLET_RECHARGE_Q)
        recharge_txs = _filter_qs(recharge_txs)
        recharge_agg = recharge_txs.aggregate(
            total=Sum('amount'),
            count=Count('id'),
        )

        deposit_payments = _filter_qs(
            Payment.objects.filter(payment_type='deposit', status='succeeded')
        )
        deposit_agg = deposit_payments.aggregate(
            total=Sum('amount'),
            count=Count('id'),
        )

        total_recharges = _dec(recharge_agg['total']) + _dec(deposit_agg['total'])
        recharge_count = (recharge_agg['count'] or 0) + (deposit_agg['count'] or 0)

        # —— Withdrawals ——
        withdrawal_qs = _filter_qs(WithdrawalRequest.objects.all())
        withdrawals_by_status = list(
            withdrawal_qs.values('status')
            .annotate(count=Count('id'), total=Sum('amount'), fees=Sum('processing_fee'))
            .order_by('-count')
        )
        completed_withdrawals = withdrawal_qs.filter(status='completed').aggregate(
            total=Sum('amount'),
            net=Sum('net_amount'),
            fees=Sum('processing_fee'),
            count=Count('id'),
        )
        pending_withdrawals = withdrawal_qs.filter(
            status__in=('pending', 'approved', 'processing')
        ).aggregate(total=Sum('amount'), count=Count('id'))

        # Lifetime wallet withdrawn (all time, for reference)
        lifetime_withdrawn = Wallet.objects.aggregate(t=Sum('total_withdrawn'))['t']

        # —— Platform fees (authoritative: fee audit log) ——
        fee_qs = FeeTransaction.objects.filter(status=FeeTransaction.Status.APPLIED)
        fee_qs = _filter_qs(fee_qs)
        fees_by_type = list(
            fee_qs.values('fee_type')
            .annotate(total=Sum('fee_amount'), count=Count('id'))
            .order_by('-total')
        )
        total_fees = _dec(fee_qs.aggregate(t=Sum('fee_amount'))['t'])

        reversed_fees = _dec(
            _filter_qs(
                FeeTransaction.objects.filter(status=FeeTransaction.Status.REVERSED)
            ).aggregate(t=Sum('fee_amount'))['t']
        )

        # Payment-recorded platform fees (cross-check)
        payment_fee_qs = _filter_qs(Payment.objects.exclude(platform_fee=0))
        payment_platform_fees = _dec(
            payment_fee_qs.aggregate(t=Sum('platform_fee'))['t']
        )

        # —— Task GMV & tasker payouts ——
        task_payments = _filter_qs(
            Payment.objects.filter(
                payment_type='task_payment',
                status__in=('succeeded', 'held', 'released'),
            )
        )
        gmv = _dec(task_payments.aggregate(t=Sum('amount'))['t'])
        tasker_net_paid = _dec(
            _filter_qs(
                Payment.objects.filter(
                    payment_type='task_payment',
                    status='released',
                )
            ).aggregate(t=Sum(Coalesce('net_amount', 'amount')))['t']
        )

        released_escrow = _filter_qs(Escrow.objects.filter(released_at__isnull=False))
        escrow_released_to_taskers = _dec(
            released_escrow.aggregate(t=Sum('net_amount'))['t']
        )

        # —— Refunds ——
        refund_payments = _filter_qs(
            Payment.objects.filter(status__in=('refunded', 'partially_refunded'))
        )
        refunds_total = _dec(refund_payments.aggregate(t=Sum('amount'))['t'])
        refund_records = _filter_qs(Refund.objects.all())
        refund_model_total = _dec(refund_records.aggregate(t=Sum('amount'))['t'])

        # —— Escrow snapshot (current balances, not period-scoped) ——
        escrow_by_status = list(
            Escrow.objects.values('status')
            .annotate(count=Count('id'), total=Sum('amount'), fees=Sum('platform_fee'))
            .order_by('-count')
        )
        escrow_held_now = _dec(
            Escrow.objects.filter(
                status__in=(
                    PENDING_PAYMENT,
                    FUNDED,
                    IN_PROGRESS,
                    SUBMITTED,
                    COMPLETED,
                    DISPUTED,
                )
            ).aggregate(t=Sum('amount'))['t']
        )
        wallet_held = _dec(Wallet.objects.aggregate(t=Sum('held_balance'))['t'])
        wallet_available = _dec(Wallet.objects.aggregate(t=Sum('available_balance'))['t'])

        # —— Profit estimate ——
        # Platform profit ≈ net fees collected minus recorded refunds of platform share
        net_platform_fees = total_fees - reversed_fees
        estimated_profit = net_platform_fees - refunds_total * Decimal('0')
        # Conservative: profit = fees (refunds on tasks don't always claw back fees)

        # —— Payments breakdown ——
        payments_by_status = list(
            _filter_qs(Payment.objects.all())
            .values('status')
            .annotate(count=Count('id'), total=Sum('amount'))
            .order_by('-count')
        )
        payments_by_type = list(
            _filter_qs(Payment.objects.all())
            .values('payment_type')
            .annotate(count=Count('id'), total=Sum('amount'))
            .order_by('-total')
        )

        # —— Disputes ——
        dispute_qs = _filter_qs(Dispute.objects.all())
        disputes_by_status = list(
            dispute_qs.values('status')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        open_disputes = dispute_qs.filter(status__in=('open', 'under_review', 'escalated')).count()

        # —— Growth / overview ——
        overview = DashboardService.get_platform_overview()
        growth = DashboardService.get_growth_metrics(
            days=period_days if period_days else 3650
        )

        # —— Daily trend (fees + task volume) ——
        trend_days = min(period_days or 30, 30)
        trend_start = timezone.now() - timedelta(days=trend_days)
        daily_fees = list(
            FeeTransaction.objects.filter(
                status=FeeTransaction.Status.APPLIED,
                created_at__gte=trend_start,
            )
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(total=Sum('fee_amount'), count=Count('id'))
            .order_by('day')
        )
        daily_tasks = list(
            Task.objects.filter(created_at__gte=trend_start)
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )

        charts = BusinessMetricsService._build_charts(
            daily_fees=daily_fees,
            daily_tasks=daily_tasks,
            fees_by_type=fees_by_type,
            payments_by_status=payments_by_status,
            escrow_by_status=escrow_by_status,
            withdrawals_by_status=withdrawals_by_status,
            growth=growth,
            recharges_total=_f(total_recharges),
            withdrawals_total=_f(completed_withdrawals['total']),
            net_fees=_f(net_platform_fees),
            refunds_total=_f(refunds_total),
            tasker_payouts=_f(max(tasker_net_paid, escrow_released_to_taskers)),
            gmv=_f(gmv),
        )

        return {
            'currency': DEFAULT_CURRENCY,
            'period_days': period_days,
            'period_label': period_label,
            'generated_at': timezone.now(),
            'kpis': [
                {
                    'label': 'Platform revenue (fees)',
                    'value': _f(net_platform_fees),
                    'hint': f'Applied fees − reversed ({_f(reversed_fees)} reversed)',
                },
                {
                    'label': 'Estimated profit',
                    'value': _f(estimated_profit),
                    'hint': 'Net platform fees (see fee breakdown)',
                },
                {
                    'label': 'Task GMV',
                    'value': _f(gmv),
                    'hint': 'Task payments funded / held / released',
                },
                {
                    'label': 'Paid to taskers',
                    'value': _f(max(tasker_net_paid, escrow_released_to_taskers)),
                    'hint': 'Released task payments & escrow',
                },
                {
                    'label': 'Total recharges',
                    'value': _f(total_recharges),
                    'hint': f'{recharge_count} top-ups (wallet + deposits)',
                },
                {
                    'label': 'Total withdrawals',
                    'value': _f(completed_withdrawals['total']),
                    'hint': f'{completed_withdrawals["count"] or 0} completed payouts',
                },
                {
                    'label': 'Refunds',
                    'value': _f(refunds_total),
                    'hint': f'Refund records: {_f(refund_model_total)}',
                },
                {
                    'label': 'Held in escrow',
                    'value': _f(escrow_held_now),
                    'hint': f'Wallet held balances: {_f(wallet_held)}',
                },
            ],
            'financial': {
                'net_platform_fees': _f(net_platform_fees),
                'total_fees_applied': _f(total_fees),
                'fees_reversed': _f(reversed_fees),
                'payment_platform_fees': _f(payment_platform_fees),
                'gmv': _f(gmv),
                'tasker_payouts': _f(max(tasker_net_paid, escrow_released_to_taskers)),
                'refunds': _f(refunds_total),
                'estimated_profit': _f(estimated_profit),
            },
            'recharges': {
                'total': _f(total_recharges),
                'wallet_credits': _f(recharge_agg['total']),
                'wallet_count': recharge_agg['count'] or 0,
                'deposit_payments': _f(deposit_agg['total']),
                'deposit_count': deposit_agg['count'] or 0,
            },
            'withdrawals': {
                'completed_total': _f(completed_withdrawals['total']),
                'completed_net': _f(completed_withdrawals['net']),
                'completed_fees': _f(completed_withdrawals['fees']),
                'completed_count': completed_withdrawals['count'] or 0,
                'pending_total': _f(pending_withdrawals['total']),
                'pending_count': pending_withdrawals['count'] or 0,
                'lifetime_wallet_withdrawn': _f(lifetime_withdrawn),
                'by_status': withdrawals_by_status,
            },
            'fees': {
                'total_applied': _f(total_fees),
                'by_type': fees_by_type,
            },
            'escrow': {
                'held_now': _f(escrow_held_now),
                'wallet_held': _f(wallet_held),
                'wallet_available': _f(wallet_available),
                'by_status': escrow_by_status,
            },
            'payments': {
                'by_status': payments_by_status,
                'by_type': payments_by_type,
            },
            'disputes': {
                'open': open_disputes,
                'by_status': disputes_by_status,
            },
            'overview': overview,
            'growth': growth,
            'trends': {
                'daily_fees': daily_fees,
                'daily_tasks': daily_tasks,
            },
            'charts': charts,
            'recent': {
                'recharges': list(
                    recharge_txs.select_related('wallet__user')
                    .order_by('-created_at')[:10]
                    .values(
                        'created_at',
                        'amount',
                        'description',
                        'wallet__user__email',
                    )
                ),
                'withdrawals': list(
                    withdrawal_qs.select_related('wallet__user')
                    .order_by('-created_at')[:10]
                    .values(
                        'created_at',
                        'amount',
                        'status',
                        'withdrawal_method',
                        'wallet__user__email',
                    )
                ),
                'fees': list(
                    fee_qs.select_related('user', 'task')
                    .order_by('-created_at')[:10]
                    .values('created_at', 'fee_type', 'fee_amount', 'user__email', 'status')
                ),
            },
        }
