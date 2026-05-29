from django.contrib import admin

from .models import AccountSuspensionLog, PlatformRule, RuleEvaluationLog, RulePolicy


@admin.register(RulePolicy)
class RulePolicyAdmin(admin.ModelAdmin):
    list_display = [
        'category', 'slug', 'name', 'is_active', 'priority', 'enforcement', 'updated_at',
    ]
    list_filter = ['category', 'is_active', 'enforcement']
    search_fields = ['name', 'slug', 'description']
    list_editable = ['is_active', 'priority']
    ordering = ['category', '-priority', 'slug']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        (None, {'fields': ('category', 'slug', 'name', 'description', 'is_active', 'priority', 'enforcement')}),
        ('Triggers & filters', {'fields': ('event_triggers', 'conditions')}),
        ('Parameters', {'fields': ('parameters',), 'description': 'JSON thresholds — see RULE_ENGINE.md'}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(RuleEvaluationLog)
class RuleEvaluationLogAdmin(admin.ModelAdmin):
    list_display = ['event', 'allowed', 'actor', 'task', 'policies_evaluated', 'created_at']
    list_filter = ['allowed', 'event', 'created_at']
    search_fields = ['event', 'actor__email']
    readonly_fields = [
        'event', 'actor', 'task', 'allowed', 'policies_evaluated',
        'violations', 'actions', 'context_snapshot', 'created_at',
    ]
    ordering = ['-created_at']


@admin.register(PlatformRule)
class PlatformRuleAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'rule_type', 'is_active', 'max_cancellations',
        'suspension_hours', 'counting_window_days', 'updated_at',
    ]
    list_filter = ['is_active']
    list_editable = ['is_active', 'max_cancellations', 'suspension_hours']


@admin.register(AccountSuspensionLog)
class AccountSuspensionLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'cancellation_count', 'suspended_until', 'lifted_at', 'created_at']
    list_filter = ['created_at']
    readonly_fields = ['user', 'rule', 'policy', 'cancellation_count', 'suspended_until', 'reason', 'created_at']
