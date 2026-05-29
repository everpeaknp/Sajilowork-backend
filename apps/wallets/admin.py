from decimal import Decimal

from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from .forms import ManualWalletCreditForm
from .models import Wallet, WalletTransaction, WithdrawalRequest, WalletFreeze, WalletLimit
from .services import WalletService


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = [
        'user_email', 'available_balance_display', 'pending_balance',
        'held_balance', 'total_balance_display', 'currency', 'status_display',
        'created_at',
    ]
    list_display_links = ['user_email']
    list_filter = ['is_active', 'is_frozen', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'id']
    readonly_fields = [
        'id', 'credit_wallet_button', 'available_balance', 'pending_balance', 'held_balance',
        'total_earned', 'total_withdrawn', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('User Information', {
            'fields': ('id', 'user', 'credit_wallet_button')
        }),
        ('Balance', {
            'fields': (
                'available_balance', 'pending_balance', 'held_balance',
                'total_earned', 'total_withdrawn', 'currency'
            )
        }),
        ('Status', {
            'fields': ('is_active', 'is_frozen', 'frozen_reason', 'frozen_at')
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<path:object_id>/credit/',
                self.admin_site.admin_view(self.credit_wallet_view),
                name='wallets_wallet_credit',
            ),
        ]
        return custom + urls

    def credit_wallet_button(self, obj):
        if not obj or not obj.pk:
            return '-'
        url = reverse('admin:wallets_wallet_credit', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}">Manual recharge (credit wallet)</a>',
            url,
        )

    credit_wallet_button.short_description = 'Manual recharge'

    def credit_wallet_view(self, request, object_id):
        wallet = self.get_object(request, object_id)
        if wallet is None:
            messages.error(request, 'Wallet not found.')
            return redirect('admin:wallets_wallet_changelist')

        if wallet.is_frozen:
            messages.error(request, 'This wallet is frozen. Unfreeze it before crediting.')
            return redirect('admin:wallets_wallet_change', wallet.pk)

        if request.method == 'POST':
            form = ManualWalletCreditForm(request.POST)
            if form.is_valid():
                amount = form.cleaned_data['amount']
                request_id = (form.cleaned_data.get('whatsapp_request_id') or '').strip()
                notes = (form.cleaned_data.get('notes') or '').strip()

                if request_id:
                    already = WalletTransaction.objects.filter(
                        wallet=wallet,
                        transaction_type='credit',
                        status='completed',
                        metadata__whatsapp_request_id=request_id,
                    ).exists()
                    if already:
                        messages.warning(
                            request,
                            f'Wallet already credited for request ID {request_id}.',
                        )
                        return redirect('admin:wallets_wallet_change', wallet.pk)

                description = 'Manual wallet recharge (admin)'
                if request_id:
                    description = f'{description} — {request_id}'

                metadata = {
                    'channel': 'admin_manual',
                    'credited_by_admin_id': str(request.user.pk),
                    'credited_by_admin_email': request.user.email,
                }
                if request_id:
                    metadata['whatsapp_request_id'] = request_id
                if notes:
                    metadata['admin_notes'] = notes

                WalletService.credit_wallet(
                    wallet,
                    Decimal(str(amount)),
                    description=description,
                    transaction_type='credit',
                    metadata=metadata,
                )
                wallet.refresh_from_db()
                messages.success(
                    request,
                    f'Credited NPR {amount} to {wallet.user.email}. '
                    f'New balance: {wallet.available_balance} {wallet.currency}.',
                )
                return redirect('admin:wallets_wallet_change', wallet.pk)
        else:
            form = ManualWalletCreditForm()

        context = {
            **self.admin_site.each_context(request),
            'title': f'Manual recharge — {wallet.user.email}',
            'wallet': wallet,
            'form': form,
            'opts': self.model._meta,
            'app_label': self.model._meta.app_label,
            'has_view_permission': self.has_view_permission(request, wallet),
            'has_change_permission': self.has_change_permission(request, wallet),
        }
        return render(request, 'admin/wallets/wallet/credit_wallet.html', context)

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    
    def available_balance_display(self, obj):
        return f"{obj.available_balance} {obj.currency}"
    available_balance_display.short_description = 'Available Balance'
    
    def total_balance_display(self, obj):
        return f"{obj.total_balance} {obj.currency}"
    total_balance_display.short_description = 'Total Balance'
    
    def status_display(self, obj):
        if obj.is_frozen:
            return format_html(
                '<span style="color: red; font-weight: bold;">🔒 Frozen</span>'
            )
        elif obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Active</span>'
            )
        else:
            return format_html(
                '<span style="color: gray; font-weight: bold;">⊗ Inactive</span>'
            )
    status_display.short_description = 'Status'


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'wallet_user', 'transaction_type', 'amount_display',
        'status_display', 'reference_number', 'created_at'
    ]
    list_filter = ['transaction_type', 'status', 'currency', 'created_at']
    search_fields = ['wallet__user__email', 'reference_number', 'description']
    readonly_fields = [
        'id', 'wallet', 'balance_before', 'balance_after',
        'reference_number', 'created_at', 'completed_at'
    ]
    
    fieldsets = (
        ('Transaction Information', {
            'fields': ('id', 'wallet', 'transaction_type', 'status')
        }),
        ('Amount', {
            'fields': ('amount', 'currency', 'balance_before', 'balance_after')
        }),
        ('Details', {
            'fields': ('description', 'notes', 'reference_number')
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'completed_at')
        }),
    )
    
    def wallet_user(self, obj):
        return obj.wallet.user.email
    wallet_user.short_description = 'User'
    
    def amount_display(self, obj):
        return f"{obj.amount} {obj.currency}"
    amount_display.short_description = 'Amount'
    
    def status_display(self, obj):
        colors = {
            'pending': 'orange',
            'completed': 'green',
            'failed': 'red',
            'cancelled': 'gray',
            'reversed': 'purple'
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = 'Status'


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    change_form_template = 'admin/wallets/withdrawalrequest/change_form.html'

    list_display = [
        'id', 'wallet_user', 'amount_display', 'net_amount_display',
        'withdrawal_method', 'status_display', 'created_at'
    ]
    list_filter = ['status', 'withdrawal_method', 'currency', 'created_at']
    search_fields = ['wallet__user__email', 'payment_reference']
    readonly_fields = [
        'id', 'wallet', 'status', 'approval_actions_help', 'processing_fee', 'net_amount',
        'approved_by', 'approved_at', 'created_at', 'updated_at', 'completed_at',
    ]
    actions = ['approve_withdrawals', 'reject_withdrawals', 'apply_missing_wallet_debit']

    def response_change(self, request, obj):
        """
        Handle Approve/Reject buttons rendered inside the main admin form.
        (We can't use nested <form> tags inside the change form.)
        """
        if "_approve_withdrawal" in request.POST:
            try:
                self._approve_withdrawal(obj, request.user)
                self.message_user(
                    request,
                    f'Withdrawal {obj.id} approved. Wallet debited {obj.amount} {obj.currency}.',
                    level=messages.SUCCESS,
                )
            except Exception as exc:
                self.message_user(request, str(exc), level=messages.ERROR)
            return redirect('admin:wallets_withdrawalrequest_change', obj.pk)

        if "_reject_withdrawal" in request.POST:
            try:
                self._reject_withdrawal(obj, request.user)
                self.message_user(
                    request,
                    f'Withdrawal {obj.id} rejected.',
                    level=messages.SUCCESS,
                )
            except Exception as exc:
                self.message_user(request, str(exc), level=messages.ERROR)
            return redirect('admin:wallets_withdrawalrequest_change', obj.pk)

        return super().response_change(request, obj)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<path:object_id>/approve/',
                self.admin_site.admin_view(self.approve_single_view),
                name='wallets_withdrawalrequest_approve',
            ),
            path(
                '<path:object_id>/reject/',
                self.admin_site.admin_view(self.reject_single_view),
                name='wallets_withdrawalrequest_reject',
            ),
        ]
        return custom + urls

    def approval_actions_help(self, obj):
        if not obj or not obj.pk:
            return '-'
        if obj.status == 'pending':
            return format_html(
                '<p style="margin:0 0 8px;"><strong>Pending review.</strong> '
                'Use the green <strong>Approve withdrawal</strong> or red '
                '<strong>Reject withdrawal</strong> buttons at the bottom of this page, '
                'or select this row on the <a href="{}">list page</a> and use the '
                'Actions dropdown.</p>',
                reverse('admin:wallets_withdrawalrequest_changelist'),
            )
        return format_html(
            '<p style="margin:0;">Status is <strong>{}</strong>. '
            'Approve/Reject only apply while status is <strong>Pending</strong>.</p>',
            obj.get_status_display(),
        )

    approval_actions_help.short_description = 'Approval'

    def _approve_withdrawal(self, withdrawal, admin_user):
        if withdrawal.status == 'pending':
            WalletService.process_withdrawal(withdrawal, admin_user)
            return
        if withdrawal.status in ('approved', 'processing') and not WalletService.withdrawal_debit_applied(withdrawal):
            WalletService.apply_missing_withdrawal_debit(withdrawal, admin_user)
            return
        raise ValueError('Withdrawal cannot be approved in its current state')

    def _reject_withdrawal(self, withdrawal, admin_user):
        if withdrawal.status != 'pending':
            raise ValueError('Only pending withdrawals can be rejected')
        WalletService.release_withdrawal_reservation(withdrawal)
        withdrawal.status = 'rejected'
        withdrawal.rejection_reason = withdrawal.rejection_reason or 'Rejected by admin'
        withdrawal.approved_by = admin_user
        withdrawal.approved_at = timezone.now()
        withdrawal.save(
            update_fields=[
                'status', 'rejection_reason', 'approved_by', 'approved_at', 'updated_at',
            ]
        )

    def approve_single_view(self, request, object_id):
        withdrawal = self.get_object(request, object_id)
        if withdrawal is None:
            messages.error(request, 'Withdrawal request not found.')
            return redirect('admin:wallets_withdrawalrequest_changelist')
        if request.method != 'POST':
            messages.error(request, 'Invalid request method.')
            return redirect('admin:wallets_withdrawalrequest_change', object_id)
        try:
            self._approve_withdrawal(withdrawal, request.user)
            messages.success(
                request,
                f'Withdrawal {withdrawal.id} approved. Wallet debited {withdrawal.amount} {withdrawal.currency}.',
            )
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect('admin:wallets_withdrawalrequest_change', object_id)

    def reject_single_view(self, request, object_id):
        withdrawal = self.get_object(request, object_id)
        if withdrawal is None:
            messages.error(request, 'Withdrawal request not found.')
            return redirect('admin:wallets_withdrawalrequest_changelist')
        if request.method != 'POST':
            messages.error(request, 'Invalid request method.')
            return redirect('admin:wallets_withdrawalrequest_change', object_id)
        try:
            self._reject_withdrawal(withdrawal, request.user)
            messages.success(request, f'Withdrawal {withdrawal.id} rejected.')
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect('admin:wallets_withdrawalrequest_change', object_id)

    @admin.action(description='Approve selected (debits wallet)')
    def approve_withdrawals(self, request, queryset):
        ok = 0
        for withdrawal in queryset:
            try:
                self._approve_withdrawal(withdrawal, request.user)
                ok += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f'{withdrawal.id}: {exc}',
                    level=messages.ERROR,
                )
        if ok:
            self.message_user(request, f'Processed {ok} withdrawal(s).', level=messages.SUCCESS)

    @admin.action(description='Reject selected (refunds pending reservations)')
    def reject_withdrawals(self, request, queryset):
        ok = 0
        for withdrawal in queryset.filter(status='pending'):
            try:
                self._reject_withdrawal(withdrawal, request.user)
                ok += 1
            except Exception as exc:
                self.message_user(request, f'{withdrawal.id}: {exc}', level=messages.ERROR)
        if ok:
            self.message_user(request, f'Rejected {ok} withdrawal(s).', level=messages.SUCCESS)

    @admin.action(description='Apply missing wallet debit (approved without payout)')
    def apply_missing_wallet_debit(self, request, queryset):
        ok = 0
        for withdrawal in queryset:
            if WalletService.withdrawal_debit_applied(withdrawal):
                continue
            try:
                WalletService.apply_missing_withdrawal_debit(withdrawal, request.user)
                ok += 1
            except Exception as exc:
                self.message_user(request, f'{withdrawal.id}: {exc}', level=messages.ERROR)
        if ok:
            self.message_user(
                request,
                f'Applied wallet debit for {ok} withdrawal(s). Refresh user wallet.',
                level=messages.SUCCESS,
            )

    fieldsets = (
        ('Request Information', {
            'fields': ('id', 'wallet', 'status', 'approval_actions_help')
        }),
        ('Amount', {
            'fields': ('amount', 'currency', 'processing_fee', 'net_amount')
        }),
        ('Method', {
            'fields': ('withdrawal_method',)
        }),
        ('Bank Details', {
            'fields': (
                'bank_account_name', 'bank_account_number',
                'bank_name', 'bank_routing_number'
            ),
            'classes': ('collapse',)
        }),
        ('Processing', {
            'fields': (
                'approved_by', 'approved_at', 'rejection_reason',
                'failure_reason', 'payment_reference'
            )
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'completed_at')
        }),
    )
    
    def wallet_user(self, obj):
        return obj.wallet.user.email
    wallet_user.short_description = 'User'
    
    def amount_display(self, obj):
        return f"{obj.amount} {obj.currency}"
    amount_display.short_description = 'Amount'
    
    def net_amount_display(self, obj):
        return f"{obj.net_amount} {obj.currency}"
    net_amount_display.short_description = 'Net Amount'
    
    def status_display(self, obj):
        colors = {
            'pending': 'orange',
            'approved': 'blue',
            'processing': 'purple',
            'completed': 'green',
            'rejected': 'red',
            'cancelled': 'gray',
            'failed': 'darkred'
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = 'Status'


@admin.register(WalletFreeze)
class WalletFreezeAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'wallet_user', 'reason', 'frozen_by_email',
        'is_active', 'frozen_at', 'unfrozen_at'
    ]
    list_filter = ['reason', 'is_active', 'frozen_at']
    search_fields = ['wallet__user__email', 'description']
    readonly_fields = [
        'id', 'wallet', 'frozen_by', 'unfrozen_by',
        'frozen_at', 'unfrozen_at'
    ]
    
    fieldsets = (
        ('Freeze Information', {
            'fields': ('id', 'wallet', 'reason', 'description', 'is_active')
        }),
        ('Actions', {
            'fields': ('frozen_by', 'unfrozen_by')
        }),
        ('Timestamps', {
            'fields': ('frozen_at', 'unfrozen_at')
        }),
    )
    
    def wallet_user(self, obj):
        return obj.wallet.user.email
    wallet_user.short_description = 'User'
    
    def frozen_by_email(self, obj):
        return obj.frozen_by.email if obj.frozen_by else '-'
    frozen_by_email.short_description = 'Frozen By'


@admin.register(WalletLimit)
class WalletLimitAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'wallet_user', 'limit_type', 'amount_display',
        'is_active', 'created_at'
    ]
    list_filter = ['limit_type', 'is_active', 'currency', 'created_at']
    search_fields = ['wallet__user__email']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Limit Information', {
            'fields': ('id', 'wallet', 'limit_type', 'is_active')
        }),
        ('Amount', {
            'fields': ('amount', 'currency')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def wallet_user(self, obj):
        return obj.wallet.user.email
    wallet_user.short_description = 'User'
    
    def amount_display(self, obj):
        return f"{obj.amount} {obj.currency}"
    amount_display.short_description = 'Limit Amount'
