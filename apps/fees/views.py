from decimal import Decimal

from django.db.models import Count, Sum
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from .engine import FeeContext, FeeEngine
from .models import FeeRule, FeeTransaction
from .serializers import (
    FeeCalculateInputSerializer,
    FeeCalculateOutputSerializer,
    WithdrawalFeeInputSerializer,
    CancellationFeeInputSerializer,
    build_fee_context,
)


class FeeCalculateViewSet(viewsets.ViewSet):
    """
    Public fee calculation API (server-side only — clients must not compute fees).
    """

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'], url_path='calculate')
    def calculate(self, request):
        """
        POST /api/v1/fees/calculate/

        Body: { "task_amount": 5000, ...optional context }
        """
        serializer = FeeCalculateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        ctx = build_fee_context(data)
        ctx.user_id = str(request.user.pk)

        breakdown = FeeEngine.calculate_task_settlement(
            data['task_amount'],
            ctx,
            log=data.get('log', False),
        )

        output = {
            'task_amount': breakdown['task_amount'],
            'commission': breakdown['commission'],
            'escrow': breakdown['escrow'],
            'tax': breakdown['tax'],
            'discount': breakdown['discount'],
            'total_customer_pays': breakdown['total_customer_pays'],
            'worker_receives': breakdown['worker_receives'],
            'platform_profit': breakdown['platform_profit'],
            'currency': breakdown['currency'],
            'lines': breakdown.get('lines', {}),
            'tasker_commission_percent': breakdown.get('tasker_commission_percent'),
            # Legacy fields for existing frontend
            'gross_amount': breakdown['gross_amount'],
            'net_amount': breakdown['net_amount'],
            'platform_fee': breakdown['platform_fee'],
            'processing_fee': breakdown['processing_fee'],
            'poster_total_held': breakdown['poster_total_held'],
            'fees_enabled': breakdown['fees_enabled'],
        }

        out = FeeCalculateOutputSerializer(output)
        return Response(out.data)

    @action(detail=False, methods=['post'], url_path='withdrawal')
    def withdrawal(self, request):
        serializer = WithdrawalFeeInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        line = FeeEngine.calculate_withdrawal(
            data['amount'],
            data['withdrawal_method'],
        )
        net = Decimal(str(data['amount'])) - line.amount
        return Response({
            'withdrawal_fee': line.amount,
            'net_amount': net,
            'rule_id': line.rule_id,
            'rule_name': line.rule_name,
        })

    @action(detail=False, methods=['post'], url_path='cancellation')
    def cancellation(self, request):
        serializer = CancellationFeeInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        line = FeeEngine.calculate_cancellation(
            data['task_amount'],
            data['stage'],
        )
        return Response({
            'cancellation_fee': line.amount,
            'stage': data['stage'],
            'rule_id': line.rule_id,
            'rule_name': line.rule_name,
        })

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def analytics(self, request):
        """Admin: platform revenue from applied fee logs."""
        qs = FeeTransaction.objects.filter(status=FeeTransaction.Status.APPLIED)
        by_type = qs.values('fee_type').annotate(
            total=Sum('fee_amount'),
            count=Count('id'),
        )
        total = qs.aggregate(total=Sum('fee_amount'))['total'] or Decimal('0')
        return Response({
            'total_platform_fees': str(total),
            'by_fee_type': list(by_type),
        })

    @action(detail=False, methods=['get'], url_path='platform-revenue', permission_classes=[IsAdminUser])
    def platform_revenue(self, request):
        """
        GET /api/v1/fees/platform-revenue/

        Alias for analytics (kept for developer-facing API naming).
        """
        return self.analytics(request)


class FeeRuleViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only list of active rules for transparency (admin uses Django admin)."""

    permission_classes = [IsAdminUser]
    queryset = FeeRule.objects.filter(is_active=True).order_by('-priority')
    serializer_class = None

    def list(self, request, *args, **kwargs):
        rules = self.get_queryset()
        data = [
            {
                'id': str(r.id),
                'name': r.name,
                'fee_type': r.fee_type,
                'value_type': r.value_type,
                'value': str(r.value),
                'priority': r.priority,
            }
            for r in rules
        ]
        return Response(data)
