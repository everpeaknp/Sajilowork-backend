from decimal import Decimal

from django.contrib import admin
from django.db.models import Sum
from django.urls import path
from django.shortcuts import render
from django.utils.html import format_html

from .models import FeeRule, FeeTransaction


@admin.register(FeeRule)
class FeeRuleAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'fee_type',
        'applies_to',
        'value_display',
        'priority',
        'is_active',
        'category',
        'user_tier',
        'cancellation_stage',
        'withdrawal_method',
        'updated_at',
    ]
    list_filter = ['fee_type', 'is_active', 'value_type', 'category']
    search_fields = ['name']
    list_editable = ['is_active', 'priority']
    ordering = ['-priority', 'fee_type']

    fieldsets = (
        ('Rule', {
            'fields': (
                'name',
                'fee_type',
                'applies_to',
                'value_type',
                'value',
                'is_active',
                'priority',
                'currency',
                'start_date',
                'end_date',
            ),
        }),
        ('Constraints', {
            'fields': ('min_amount', 'max_amount'),
        }),
        ('Targeting (optional)', {
            'fields': (
                'category',
                'user_tier',
                'cancellation_stage',
                'withdrawal_method',
            ),
            'description': 'Leave blank to apply to all matching transactions.',
        }),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
    readonly_fields = ['created_at', 'updated_at']

    def value_display(self, obj):
        if obj.value_type == FeeRule.ValueType.PERCENTAGE:
            return f'{obj.value}%'
        return f'{obj.currency} {obj.value}'

    value_display.short_description = 'Value'


@admin.register(FeeTransaction)
class FeeTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'created_at',
        'fee_type',
        'fee_amount',
        'currency',
        'base_amount',
        'rule_used',
        'status',
        'user',
        'task',
    ]
    list_filter = ['fee_type', 'status', 'currency', 'created_at']
    search_fields = ['user__email', 'task__title', 'rule_used__name']
    readonly_fields = [
        'id',
        'task',
        'user',
        'payment',
        'withdrawal_request',
        'fee_type',
        'base_amount',
        'fee_amount',
        'currency',
        'rule_used',
        'rule_snapshot',
        'status',
        'metadata',
        'created_at',
    ]
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        applied = FeeTransaction.objects.filter(status=FeeTransaction.Status.APPLIED)
        extra_context['fee_revenue_total'] = applied.aggregate(
            t=Sum('fee_amount')
        )['t'] or Decimal('0')
        extra_context['fee_revenue_by_type'] = list(
            applied.values('fee_type').annotate(total=Sum('fee_amount')).order_by('-total')
        )
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                'revenue-dashboard/',
                self.admin_site.admin_view(self.revenue_dashboard_view),
                name='fees_feetransaction_revenue',
            ),
        ]
        return custom + urls

    def revenue_dashboard_view(self, request):
        applied = FeeTransaction.objects.filter(status=FeeTransaction.Status.APPLIED)
        by_type = list(
            applied.values('fee_type')
            .annotate(total=Sum('fee_amount'))
            .order_by('-total')
        )
        total = applied.aggregate(t=Sum('fee_amount'))['t'] or Decimal('0')
        recent = applied.select_related('user', 'task', 'rule_used')[:50]
        context = {
            **self.admin_site.each_context(request),
            'title': 'Platform fee revenue',
            'total': total,
            'by_type': by_type,
            'recent': recent,
        }
        return render(request, 'admin/fees/revenue_dashboard.html', context)
