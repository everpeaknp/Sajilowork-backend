from decimal import Decimal

from rest_framework import serializers

from .engine import FeeContext, FeeEngine
from .models import FeeRule


class FeeCalculateInputSerializer(serializers.Serializer):
    task_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    category_id = serializers.UUIDField(required=False, allow_null=True)
    listing_kind = serializers.ChoiceField(
        choices=['task', 'project', 'service', 'job'],
        required=False,
        allow_blank=True,
        default='',
    )
    user_tier = serializers.CharField(required=False, allow_blank=True, default='')
    cancellation_stage = serializers.CharField(required=False, allow_blank=True, default='')
    withdrawal_method = serializers.CharField(required=False, allow_blank=True, default='')
    payment_method = serializers.CharField(required=False, allow_blank=True, default='wallet')
    log = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if attrs.get('cancellation_stage') and not attrs.get('task_amount'):
            pass
        return attrs


class FeeCalculateOutputSerializer(serializers.Serializer):
    """
    Fee breakdown returned by `POST /api/v1/fees/calculate/`.

    Keep this serializer aligned with `FeeCalculateViewSet.calculate()` so Swagger
    shows the correct JSON output structure.
    """

    task_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    commission = serializers.DecimalField(max_digits=12, decimal_places=2)
    escrow = serializers.DecimalField(max_digits=12, decimal_places=2)
    tax = serializers.DecimalField(max_digits=12, decimal_places=2)
    discount = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_customer_pays = serializers.DecimalField(max_digits=12, decimal_places=2)
    worker_receives = serializers.DecimalField(max_digits=12, decimal_places=2)
    platform_profit = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()

    # Optional detailed line-items (debug/ops visibility).
    lines = serializers.DictField(child=serializers.DictField(), required=False)
    tasker_commission_percent = serializers.DecimalField(
        max_digits=6,
        decimal_places=3,
        required=False,
        allow_null=True,
    )

    # Legacy fields used by existing frontend pages.
    gross_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    net_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    platform_fee = serializers.DecimalField(max_digits=12, decimal_places=2)
    processing_fee = serializers.DecimalField(max_digits=12, decimal_places=2)
    poster_total_held = serializers.DecimalField(max_digits=12, decimal_places=2)
    fees_enabled = serializers.BooleanField()


class WithdrawalFeeInputSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    withdrawal_method = serializers.CharField()


class CancellationFeeInputSerializer(serializers.Serializer):
    task_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    stage = serializers.CharField()


class WithdrawalFeeOutputSerializer(serializers.Serializer):
    withdrawal_fee = serializers.DecimalField(max_digits=12, decimal_places=2)
    net_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    rule_id = serializers.UUIDField(allow_null=True, required=False)
    rule_name = serializers.CharField(allow_blank=True, required=False)


class CancellationFeeOutputSerializer(serializers.Serializer):
    cancellation_fee = serializers.DecimalField(max_digits=12, decimal_places=2)
    stage = serializers.CharField()
    rule_id = serializers.UUIDField(allow_null=True, required=False)
    rule_name = serializers.CharField(allow_blank=True, required=False)


class FeeRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeRule
        fields = [
            'id',
            'name',
            'fee_type',
            'applies_to',
            'value_type',
            'value',
            'priority',
            'min_amount',
            'max_amount',
            'category',
            'listing_kind',
            'user_tier',
            'cancellation_stage',
            'withdrawal_method',
            'currency',
            'start_date',
            'end_date',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


def build_fee_context(validated_data) -> FeeContext:
    return FeeContext(
        category_id=str(validated_data['category_id']) if validated_data.get('category_id') else None,
        listing_kind=validated_data.get('listing_kind', '') or '',
        user_tier=validated_data.get('user_tier', ''),
        cancellation_stage=validated_data.get('cancellation_stage', ''),
        withdrawal_method=validated_data.get('withdrawal_method', ''),
        payment_method=validated_data.get('payment_method', 'wallet'),
    )
