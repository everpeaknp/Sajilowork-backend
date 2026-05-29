from rest_framework import serializers

from .models import PlatformRule, RuleCategory, RulePolicy


class RulePolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = RulePolicy
        fields = [
            'id',
            'category',
            'slug',
            'name',
            'description',
            'is_active',
            'priority',
            'enforcement',
            'event_triggers',
            'conditions',
            'parameters',
            'updated_at',
        ]
        read_only_fields = fields


class RulePolicyAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = RulePolicy
        fields = [
            'id',
            'category',
            'slug',
            'name',
            'description',
            'is_active',
            'priority',
            'enforcement',
            'event_triggers',
            'conditions',
            'parameters',
        ]
        read_only_fields = ['id', 'category', 'slug']


class RuleCategorySerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()


class PlatformRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformRule
        fields = [
            'id',
            'rule_type',
            'name',
            'description',
            'is_active',
            'max_cancellations',
            'suspension_hours',
            'counting_window_days',
            'applies_to_customers',
            'applies_to_taskers',
            'updated_at',
        ]
        read_only_fields = fields


class PlatformRuleAdminWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformRule
        fields = [
            'id',
            'rule_type',
            'name',
            'description',
            'is_active',
            'max_cancellations',
            'suspension_hours',
            'counting_window_days',
            'applies_to_customers',
            'applies_to_taskers',
        ]
        read_only_fields = ['id', 'rule_type']
