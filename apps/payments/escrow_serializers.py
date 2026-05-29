from rest_framework import serializers


class EscrowInitiateSerializer(serializers.Serializer):
    bid_id = serializers.UUIDField()
    provider = serializers.ChoiceField(choices=['esewa', 'khalti', 'wallet'])
    idempotency_key = serializers.CharField(max_length=128)
    success_url = serializers.URLField()
    failure_url = serializers.URLField()


class EscrowVerifySerializer(serializers.Serializer):
    transaction_id = serializers.CharField(max_length=128)
    provider = serializers.ChoiceField(choices=['esewa', 'khalti'])
    pidx = serializers.CharField(max_length=128, required=False, allow_blank=True)
    idempotency_key = serializers.CharField(max_length=128, required=False, allow_blank=True)


class EscrowReleaseSerializer(serializers.Serializer):
    task_id = serializers.UUIDField()
    force = serializers.BooleanField(default=False, required=False)


class EscrowRefundSerializer(serializers.Serializer):
    task_id = serializers.UUIDField()
    reason = serializers.CharField(required=False, allow_blank=True, max_length=2000)
