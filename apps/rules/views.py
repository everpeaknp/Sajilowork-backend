from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from .models import PlatformRule, RuleCategory, RuleEvaluationLog, RulePolicy
from .serializers import (
    PlatformRuleAdminWriteSerializer,
    PlatformRuleSerializer,
    RuleCategorySerializer,
    RulePolicyAdminSerializer,
    RulePolicySerializer,
)
from .services import ModerationService


class RulePolicyViewSet(viewsets.ModelViewSet):
    """
    Rule engine policies API.

    - GET /api/v1/rules/policies/ — list policies
    - GET /api/v1/rules/policies/{category}/{slug}/ — retrieve by category+slug
    - PATCH (admin) — update parameters
    """

    queryset = RulePolicy.objects.all().order_by('category', '-priority')
    lookup_field = 'slug'
    http_method_names = ['get', 'head', 'options', 'put', 'patch']

    def get_permissions(self):
        if self.action in ('update', 'partial_update'):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.request.user.is_staff and self.action in ('update', 'partial_update'):
            return RulePolicyAdminSerializer
        return RulePolicySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        if not self.request.user.is_staff:
            qs = qs.filter(is_active=True)
        return qs

    def list(self, request, *args, **kwargs):
        serializer = RulePolicySerializer(self.get_queryset(), many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        category = request.query_params.get('category')
        slug = kwargs.get('slug')
        if category:
            policy = RulePolicy.objects.filter(category=category, slug=slug).first()
            if not policy:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
            return Response(RulePolicySerializer(policy).data)
        return Response(RulePolicySerializer(self.get_object()).data)

    @action(detail=False, methods=['get'], url_path='categories')
    def categories(self, request):
        data = [{'value': c.value, 'label': c.label} for c in RuleCategory]
        return Response(data)

    @action(
        detail=False,
        methods=['get'],
        url_path='public-limits',
        permission_classes=[AllowAny],
    )
    def public_limits(self, request):
        """
        Public limits used by the frontend to validate forms.
        Values are sourced from active RulePolicy.parameters.
        """
        from .policy_store import get_active_policy_parameters

        task_budget = get_active_policy_parameters(RuleCategory.OFFER, "task_budget_limits")
        recharge = get_active_policy_parameters(RuleCategory.WALLET, "recharge_amount_limits")
        withdrawal = get_active_policy_parameters(RuleCategory.WITHDRAWAL, "withdrawal_amount_limits")

        def to_number(v):
            try:
                return float(v)
            except Exception:
                return None

        return Response(
            {
                "task_budget": {
                    "min": to_number(task_budget.get("min_budget_npr")),
                    "max": to_number(task_budget.get("max_budget_npr")),
                    "currency": "NPR",
                },
                "wallet_recharge": {
                    "min": to_number(recharge.get("min_recharge_amount")),
                    "max": to_number(recharge.get("max_recharge_amount")),
                    "currency": "NPR",
                },
                "wallet_withdrawal": {
                    "min": to_number(withdrawal.get("min_withdrawal_amount_npr")),
                    "max": to_number(withdrawal.get("max_withdrawal_amount_npr")),
                    "currency": "NPR",
                },
            }
        )

    @action(detail=False, methods=['get'], url_path='evaluation-logs', permission_classes=[IsAdminUser])
    def evaluation_logs(self, request):
        logs = RuleEvaluationLog.objects.all()[:100]
        data = [
            {
                'id': str(log.id),
                'event': log.event,
                'allowed': log.allowed,
                'policies_evaluated': log.policies_evaluated,
                'violations': log.violations,
                'created_at': log.created_at,
            }
            for log in logs
        ]
        return Response(data)


class PlatformRuleViewSet(viewsets.ModelViewSet):
    """Legacy moderation rules (auto-suspend cancellations)."""

    queryset = PlatformRule.objects.all().order_by('rule_type')
    lookup_field = 'rule_type'
    http_method_names = ['get', 'head', 'options', 'put', 'patch']

    def get_permissions(self):
        if self.action in ('update', 'partial_update'):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.request.user.is_staff and self.action in ('update', 'partial_update'):
            return PlatformRuleAdminWriteSerializer
        return PlatformRuleSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_staff:
            return qs
        return qs.filter(is_active=True)

    def list(self, request, *args, **kwargs):
        return Response(PlatformRuleSerializer(self.get_queryset(), many=True).data)

    @action(detail=False, methods=['get'], url_path='my-cancellation-status')
    def my_cancellation_status(self, request):
        rule = ModerationService.get_active_auto_suspend_rule()
        if not rule:
            return Response({
                'rule_active': False,
                'cancellation_count': 0,
                'max_cancellations': None,
                'account_suspended': request.user.account_suspended,
                'suspended_until': getattr(request.user, 'suspended_until', None),
            })

        count = ModerationService.count_user_cancellations(request.user, rule)
        user = ModerationService.refresh_suspension_state(request.user)
        return Response({
            'rule_active': True,
            'cancellation_count': count,
            'max_cancellations': rule.max_cancellations,
            'remaining_before_suspend': max(0, rule.max_cancellations - count),
            'suspension_hours': rule.suspension_hours,
            'counting_window_days': rule.counting_window_days,
            'account_suspended': user.account_suspended,
            'suspended_until': user.suspended_until,
            'suspension_reason': user.suspension_reason or None,
        })
