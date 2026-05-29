from datetime import timedelta
from decimal import Decimal

from django.contrib import admin
from django.db.models import Count, Sum
from django.shortcuts import render
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html

from apps.dashboard.admin_charts import (
    REPORT_PERIOD_CHOICES,
    parse_report_period,
    rows_to_chart,
)
from apps.dashboard.services import DashboardService

from .models import (
    Payment,
    PaymentMethod,
    Refund,
    Payout,
    Transaction,
    PlatformFeeSettings,
    Escrow,
    PaymentTransaction,
    EscrowAuditLog,
)





try:

    admin.site.unregister(PlatformFeeSettings)

except admin.sites.NotRegistered:

    pass





@admin.register(Payment)

class PaymentAdmin(admin.ModelAdmin):

    list_display = [

        'id', 'payer_link', 'payee_link', 'amount_display', 'payment_type',

        'payment_method', 'status_badge', 'is_escrowed', 'created_at'

    ]

    list_filter = ['status', 'payment_type', 'payment_method', 'is_escrowed', 'created_at']

    search_fields = ['id', 'payer__email', 'payee__email', 'description']

    readonly_fields = [

        'id', 'net_amount', 'refund_amount', 'refunded_at',

        'created_at', 'updated_at', 'completed_at'

    ]



    fieldsets = (

        ('Basic Information', {

            'fields': ('id', 'payer', 'payee', 'content_type', 'object_id')

        }),

        ('Payment Details', {

            'fields': (

                'amount', 'currency', 'payment_type', 'payment_method', 'status',

                'description', 'metadata'

            )

        }),

        ('Fees', {

            'fields': ('platform_fee', 'payment_processing_fee', 'net_amount')

        }),

        ('Escrow', {

            'fields': ('is_escrowed', 'escrow_released_at', 'escrow_release_scheduled_at')

        }),

        ('Refund', {

            'fields': ('refund_amount', 'refund_reason', 'refunded_at')

        }),

        ('Metadata', {

            'fields': ('failure_reason', 'created_at', 'updated_at', 'completed_at')

        }),

    )



    def payer_link(self, obj):

        if obj.payer:

            return format_html(

                '<a href="/admin/users/user/{}/change/">{}</a>',

                obj.payer.id, obj.payer.get_full_name()

            )

        return '-'

    payer_link.short_description = 'Payer'



    def payee_link(self, obj):

        if obj.payee:

            return format_html(

                '<a href="/admin/users/user/{}/change/">{}</a>',

                obj.payee.id, obj.payee.get_full_name()

            )

        return '-'

    payee_link.short_description = 'Payee'



    def amount_display(self, obj):

        return f"{obj.amount} {obj.currency}"

    amount_display.short_description = 'Amount'



    def status_badge(self, obj):

        colors = {

            'pending': 'orange',

            'processing': 'blue',

            'succeeded': 'green',

            'failed': 'red',

            'cancelled': 'gray',

            'refunded': 'purple',

            'partially_refunded': 'purple',

            'disputed': 'red',

            'held': 'orange',

            'released': 'green',

        }

        color = colors.get(obj.status, 'gray')

        return format_html(

            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',

            color, obj.get_status_display()

        )

    status_badge.short_description = 'Status'

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                'reports/',
                self.admin_site.admin_view(self.payment_reports_view),
                name='payments_payment_reports',
            ),
        ]
        return custom + urls

    def payment_reports_view(self, request):
        """Platform payment reports (Jazzmin custom link)."""
        period_days, selected_days, period_label = parse_report_period(request)
        summary_days = period_days if period_days else 3650

        financial = DashboardService.get_financial_summary(days=summary_days)
        pay_qs = Payment.objects.all()
        if period_days:
            start = timezone.now() - timedelta(days=period_days)
            pay_qs = pay_qs.filter(created_at__gte=start)

        by_status = list(
            pay_qs.values('status')
            .annotate(count=Count('id'), total=Sum('amount'))
            .order_by('-count')
        )
        by_method = list(
            pay_qs.values('payment_method')
            .annotate(count=Count('id'), total=Sum('amount'))
            .order_by('-count')
        )
        escrow_summary = list(
            Escrow.objects.values('status')
            .annotate(count=Count('id'), total=Sum('amount'))
            .order_by('-count')
        )
        held_total = Payment.objects.filter(status='held').aggregate(t=Sum('amount'))['t'] or Decimal('0')
        released_total = Payment.objects.filter(status='released').aggregate(t=Sum('amount'))['t'] or Decimal('0')
        platform_fees = Payment.objects.aggregate(t=Sum('platform_fee'))['t'] or Decimal('0')
        recent = pay_qs.select_related('payer', 'payee').order_by('-created_at')[:25]

        charts = {
            'by_status': rows_to_chart(by_status, 'status', 'total'),
            'by_method': rows_to_chart(by_method, 'payment_method', 'total'),
            'escrow': rows_to_chart(escrow_summary, 'status', 'total'),
            'financial': {
                'labels': ['Revenue', 'Platform fees', 'Refunds', 'Payouts'],
                'values': [
                    float(financial['total_revenue']),
                    float(financial['platform_fees']),
                    float(financial['refunds']),
                    float(financial['payouts']),
                ],
            },
        }
        kpis = [
            {'label': 'Total revenue', 'value': f"{financial['total_revenue']:.2f}", 'hint': period_label},
            {'label': 'Platform fees', 'value': f"{financial['platform_fees']:.2f}", 'hint': 'In selected period'},
            {'label': 'Held in escrow', 'value': f"{float(held_total):.2f}", 'hint': 'Current snapshot'},
            {'label': 'Released', 'value': f"{float(released_total):.2f}", 'hint': 'All-time released payments'},
        ]
        context = {
            **self.admin_site.each_context(request),
            'title': 'Payment reports',
            'period_label': period_label,
            'period_choices': REPORT_PERIOD_CHOICES,
            'selected_days': selected_days,
            'currency': financial.get('currency', 'NPR'),
            'financial': financial,
            'by_status': by_status,
            'by_method': by_method,
            'escrow_summary': escrow_summary,
            'held_total': held_total,
            'released_total': released_total,
            'platform_fees': platform_fees,
            'recent': recent,
            'charts': charts,
            'kpis': kpis,
        }
        return render(request, 'admin/payments/payment_reports.html', context)





@admin.register(PaymentMethod)

class PaymentMethodAdmin(admin.ModelAdmin):

    list_display = [

        'id', 'user_link', 'method_type', 'card_info', 'is_default',

        'is_verified', 'created_at'

    ]

    list_filter = ['method_type', 'is_default', 'is_verified', 'created_at']

    search_fields = ['id', 'user__email', 'card_last4', 'esewa_phone_number']

    readonly_fields = [

        'id', 'card_brand', 'card_last4', 'card_exp_month', 'card_exp_year',

        'bank_name', 'account_last4', 'created_at', 'updated_at'

    ]



    fieldsets = (

        ('Basic Information', {

            'fields': ('id', 'user', 'method_type', 'is_default', 'is_verified')

        }),

        ('Card Details (legacy)', {

            'fields': ('card_brand', 'card_last4', 'card_exp_month', 'card_exp_year'),

            'classes': ('collapse',),

        }),

        ('Bank Account Details', {

            'fields': ('bank_name', 'account_last4')

        }),

        ('eSewa', {

            'fields': ('esewa_account_name', 'esewa_phone_number'),

        }),

        ('Metadata', {

            'fields': ('billing_details', 'metadata', 'created_at', 'updated_at')

        }),

    )



    def user_link(self, obj):

        return format_html(

            '<a href="/admin/users/user/{}/change/">{}</a>',

            obj.user.id, obj.user.get_full_name()

        )

    user_link.short_description = 'User'



    def card_info(self, obj):

        if obj.method_type == 'card':

            return f"{obj.card_brand} ****{obj.card_last4}"

        if obj.method_type == 'bank_account':

            return f"{obj.bank_name} ****{obj.account_last4}"

        if obj.method_type == 'esewa':

            return str(obj)

        return '-'

    card_info.short_description = 'Details'





@admin.register(Refund)

class RefundAdmin(admin.ModelAdmin):

    list_display = [

        'id', 'payment_link', 'amount_display', 'reason', 'status_badge',

        'initiated_by_link', 'created_at'

    ]

    list_filter = ['status', 'reason', 'created_at']

    search_fields = ['id', 'payment__id', 'description']

    readonly_fields = [

        'id', 'failure_reason', 'created_at', 'updated_at', 'completed_at'

    ]



    fieldsets = (

        ('Basic Information', {

            'fields': ('id', 'payment', 'amount', 'currency', 'reason', 'description', 'status')

        }),

        ('Metadata', {

            'fields': (

                'initiated_by', 'failure_reason', 'metadata',

                'created_at', 'updated_at', 'completed_at'

            )

        }),

    )



    def payment_link(self, obj):

        return format_html(

            '<a href="/admin/payments/payment/{}/change/">{}</a>',

            obj.payment.id, obj.payment.id

        )

    payment_link.short_description = 'Payment'



    def amount_display(self, obj):

        return f"{obj.amount} {obj.currency}"

    amount_display.short_description = 'Amount'



    def initiated_by_link(self, obj):

        if obj.initiated_by:

            return format_html(

                '<a href="/admin/users/user/{}/change/">{}</a>',

                obj.initiated_by.id, obj.initiated_by.get_full_name()

            )

        return '-'

    initiated_by_link.short_description = 'Initiated By'



    def status_badge(self, obj):

        colors = {

            'pending': 'orange',

            'processing': 'blue',

            'succeeded': 'green',

            'failed': 'red',

            'cancelled': 'gray',

        }

        color = colors.get(obj.status, 'gray')

        return format_html(

            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',

            color, obj.get_status_display()

        )

    status_badge.short_description = 'Status'





@admin.register(Payout)

class PayoutAdmin(admin.ModelAdmin):

    list_display = [

        'id', 'user_link', 'amount_display', 'payout_method',

        'status_badge', 'created_at'

    ]

    list_filter = ['status', 'payout_method', 'created_at']

    search_fields = ['id', 'user__email']

    readonly_fields = [

        'id', 'processing_fee', 'net_amount',

        'failure_reason', 'created_at', 'updated_at', 'completed_at'

    ]



    fieldsets = (

        ('Basic Information', {

            'fields': ('id', 'user', 'amount', 'currency', 'payout_method', 'status')

        }),

        ('Fees', {

            'fields': ('processing_fee', 'net_amount')

        }),

        ('Metadata', {

            'fields': (

                'description', 'failure_reason', 'metadata',

                'created_at', 'updated_at', 'completed_at'

            )

        }),

    )



    def user_link(self, obj):

        return format_html(

            '<a href="/admin/users/user/{}/change/">{}</a>',

            obj.user.id, obj.user.get_full_name()

        )

    user_link.short_description = 'User'



    def amount_display(self, obj):

        return f"{obj.amount} {obj.currency}"

    amount_display.short_description = 'Amount'



    def status_badge(self, obj):

        colors = {

            'pending': 'orange',

            'processing': 'blue',

            'paid': 'green',

            'failed': 'red',

            'cancelled': 'gray',

        }

        color = colors.get(obj.status, 'gray')

        return format_html(

            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',

            color, obj.get_status_display()

        )

    status_badge.short_description = 'Status'





@admin.register(Transaction)

class TransactionAdmin(admin.ModelAdmin):

    list_display = [

        'id', 'user_link', 'transaction_type', 'amount_display',

        'balance_after', 'created_at'

    ]

    list_filter = ['transaction_type', 'created_at']

    search_fields = ['id', 'user__email', 'description']

    readonly_fields = [

        'id', 'user', 'transaction_type', 'amount', 'currency',

        'balance_before', 'balance_after', 'payment', 'refund',

        'payout', 'description', 'metadata', 'created_at'

    ]



    fieldsets = (

        ('Basic Information', {

            'fields': (

                'id', 'user', 'transaction_type', 'amount', 'currency',

                'balance_before', 'balance_after'

            )

        }),

        ('Related Objects', {

            'fields': ('payment', 'refund', 'payout')

        }),

        ('Metadata', {

            'fields': ('description', 'metadata', 'created_at')

        }),

    )



    def user_link(self, obj):

        return format_html(

            '<a href="/admin/users/user/{}/change/">{}</a>',

            obj.user.id, obj.user.get_full_name()

        )

    user_link.short_description = 'User'



    def amount_display(self, obj):

        color = 'green' if obj.amount > 0 else 'red'

        return format_html(

            '<span style="color: {};">{} {}</span>',

            color, obj.amount, obj.currency

        )

    amount_display.short_description = 'Amount'


@admin.register(Escrow)
class EscrowAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'task', 'status', 'amount', 'funding_method',
        'payer', 'payee', 'locked_at', 'created_at',
    ]
    list_filter = ['status', 'funding_method']
    search_fields = ['id', 'task__title', 'payer__email', 'payee__email']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'transaction_id', 'provider', 'status', 'amount',
        'payer', 'created_at',
    ]
    list_filter = ['provider', 'status']
    search_fields = ['transaction_id', 'idempotency_key']


@admin.register(EscrowAuditLog)
class EscrowAuditLogAdmin(admin.ModelAdmin):
    list_display = ['escrow', 'from_status', 'to_status', 'created_at']
    list_filter = ['to_status']
    readonly_fields = ['created_at']

