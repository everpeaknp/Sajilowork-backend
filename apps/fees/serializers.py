from decimal import Decimal

from rest_framework import serializers

from .engine import FeeContext, FeeEngine


class FeeCalculateInputSerializer(serializers.Serializer):
    task_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    category_id = serializers.UUIDField(required=False, allow_null=True)
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
    task_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    customer_service_fee = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    tasker_commission = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    customer_total = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    tasker_receive = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    platform_profit = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()
    lines = serializers.DictField(child=serializers.DictField(), required=False)


class WithdrawalFeeInputSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    withdrawal_method = serializers.CharField()


class CancellationFeeInputSerializer(serializers.Serializer):
    task_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    stage = serializers.CharField()


def build_fee_context(validated_data) -> FeeContext:
    return FeeContext(
        category_id=str(validated_data['category_id']) if validated_data.get('category_id') else None,
        user_tier=validated_data.get('user_tier', ''),
        cancellation_stage=validated_data.get('cancellation_stage', ''),
        withdrawal_method=validated_data.get('withdrawal_method', ''),
        payment_method=validated_data.get('payment_method', 'wallet'),
    )
