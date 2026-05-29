from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.exceptions import ValidationError
from django.conf import settings
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.utils import timezone
from .models import Wallet, WalletTransaction, WithdrawalRequest, WalletFreeze, WalletLimit
from .serializers import (
    WalletSerializer, WalletBalanceSerializer, WalletTransactionSerializer,
    WalletTransactionListSerializer, WalletTransactionCreateSerializer,
    WithdrawalRequestSerializer, WithdrawalRequestCreateSerializer,
    WithdrawalRequestListSerializer, WithdrawalApprovalSerializer,
    WalletFreezeSerializer, WalletFreezeCreateSerializer,
    WalletLimitSerializer, WalletStatsSerializer, TransactionSummarySerializer
)
from .permissions import IsWalletOwner, IsTransactionOwner, IsWithdrawalOwner
from .services import WalletService


def _recharge_whatsapp_digits() -> str:
    """Read RECHARGE_WHATSAPP_NUMBER from backend/.env (picks up edits without stale cwd)."""
    raw = ''
    env_file = settings.BASE_DIR / '.env'
    if env_file.is_file():
        try:
            from decouple import Config, RepositoryEnv

            raw = Config(RepositoryEnv(str(env_file)))(
                'RECHARGE_WHATSAPP_NUMBER',
                default='',
            )
        except Exception:
            raw = ''
    if not raw:
        raw = getattr(settings, 'RECHARGE_WHATSAPP_NUMBER', '') or ''
    return ''.join(ch for ch in str(raw) if ch.isdigit())


class WalletViewSet(viewsets.ModelViewSet):
    """
    ViewSet for wallet management
    """
    queryset = Wallet.objects.select_related('user').all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'balance':
            return WalletBalanceSerializer
        return WalletSerializer
    
    def get_permissions(self):
        if self.action in ['list', 'freeze', 'unfreeze']:
            return [IsAdminUser()]
        return [IsAuthenticated(), IsWalletOwner()]
    
    @action(detail=False, methods=['get'])
    def my_wallet(self, request):
        """Get current user's wallet"""
        wallet, created = Wallet.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(wallet)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def balance(self, request):
        """Get wallet balance"""
        wallet, created = Wallet.objects.get_or_create(user=request.user)
        serializer = WalletBalanceSerializer(wallet)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def recharge_settings(self, request):
        """Public recharge options for authenticated users (WhatsApp manual top-up)."""
        try:
            from apps.rules.models import RuleCategory
            from apps.rules.policy_store import get_active_policy_parameters

            params = get_active_policy_parameters(RuleCategory.WALLET, 'recharge_amount_limits')
            min_amt = int(params.get('min_recharge_amount') or 100)
            max_amt = int(params.get('max_recharge_amount') or 10000)
        except Exception:
            min_amt = 100
            max_amt = 10000
        return Response({
            'whatsapp_number': _recharge_whatsapp_digits(),
            'min_recharge_amount': min_amt,
            'max_recharge_amount': max_amt,
        })

    @action(detail=False, methods=['get'])
    def withdrawal_settings(self, request):
        """Public withdrawal limits for authenticated users."""
        try:
            from apps.rules.models import RuleCategory
            from apps.rules.policy_store import get_active_policy_parameters

            params = get_active_policy_parameters(RuleCategory.WITHDRAWAL, 'withdrawal_amount_limits')
            min_amt = float(params.get('min_withdrawal_amount_npr') or 10)
            max_amt = params.get('max_withdrawal_amount_npr')
            max_amt = float(max_amt) if max_amt is not None else None
        except Exception:
            min_amt = 10
            max_amt = None

        return Response({
            'min_withdrawal_amount': min_amt,
            'max_withdrawal_amount': max_amt,
            'currency': getattr(settings, 'DEFAULT_CURRENCY', 'NPR'),
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get wallet statistics"""
        wallet, created = Wallet.objects.get_or_create(user=request.user)
        
        # Get pending withdrawals
        pending_withdrawals = WithdrawalRequest.objects.filter(
            wallet=wallet,
            status__in=['pending', 'approved', 'processing']
        )
        
        stats = {
            'total_balance': wallet.total_balance,
            'available_balance': wallet.available_balance,
            'pending_balance': wallet.pending_balance,
            'held_balance': wallet.held_balance,
            'total_earned': wallet.total_earned,
            'total_withdrawn': wallet.total_withdrawn,
            'total_transactions': wallet.transactions.count(),
            'pending_withdrawals': pending_withdrawals.count(),
            'pending_withdrawals_amount': pending_withdrawals.aggregate(
                total=Sum('amount')
            )['total'] or 0,
            'currency': wallet.currency
        }
        
        serializer = WalletStatsSerializer(stats)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def freeze(self, request, pk=None):
        """Freeze a wallet (admin only)"""
        wallet = self.get_object()
        serializer = WalletFreezeCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            wallet.is_frozen = True
            wallet.frozen_reason = serializer.validated_data['description']
            wallet.frozen_at = timezone.now()
            wallet.save()
            
            # Create freeze record
            WalletFreeze.objects.create(
                wallet=wallet,
                reason=serializer.validated_data['reason'],
                description=serializer.validated_data['description'],
                frozen_by=request.user
            )
            
            return Response({'message': 'Wallet frozen successfully'})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def unfreeze(self, request, pk=None):
        """Unfreeze a wallet (admin only)"""
        wallet = self.get_object()
        
        if not wallet.is_frozen:
            return Response(
                {'error': 'Wallet is not frozen'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        wallet.is_frozen = False
        wallet.frozen_reason = ''
        wallet.frozen_at = None
        wallet.save()
        
        # Update freeze record
        active_freeze = WalletFreeze.objects.filter(
            wallet=wallet,
            is_active=True
        ).first()
        
        if active_freeze:
            active_freeze.is_active = False
            active_freeze.unfrozen_by = request.user
            active_freeze.unfrozen_at = timezone.now()
            active_freeze.save()
        
        return Response({'message': 'Wallet unfrozen successfully'})


class WalletTransactionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for wallet transactions
    """
    queryset = WalletTransaction.objects.select_related('wallet__user').all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return WalletTransactionListSerializer
        elif self.action == 'create':
            return WalletTransactionCreateSerializer
        return WalletTransactionSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            return [IsAdminUser()]
        return [IsAuthenticated(), IsTransactionOwner()]
    
    def get_queryset(self):
        """Filter transactions for current user"""
        if self.request.user.is_staff:
            return self.queryset
        
        wallet = Wallet.objects.filter(user=self.request.user).first()
        if wallet:
            return self.queryset.filter(wallet=wallet)
        return self.queryset.none()
    
    @action(detail=False, methods=['get'])
    def my_transactions(self, request):
        """Get current user's transactions"""
        wallet = Wallet.objects.filter(user=request.user).first()
        if not wallet:
            return Response([])
        
        transactions = self.queryset.filter(wallet=wallet)
        
        # Filter by type
        transaction_type = request.query_params.get('type')
        if transaction_type:
            transactions = transactions.filter(transaction_type=transaction_type)
        
        # Filter by status
        status_filter = request.query_params.get('status')
        if status_filter:
            transactions = transactions.filter(status=status_filter)
        
        page = self.paginate_queryset(transactions)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(transactions, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get transaction summary by type"""
        wallet = Wallet.objects.filter(user=request.user).first()
        if not wallet:
            return Response([])
        
        summary = WalletTransaction.objects.filter(
            wallet=wallet,
            status='completed'
        ).values('transaction_type').annotate(
            count=Count('id'),
            total_amount=Sum('amount')
        )
        
        result = []
        for item in summary:
            result.append({
                'transaction_type': item['transaction_type'],
                'count': item['count'],
                'total_amount': item['total_amount'],
                'currency': wallet.currency
            })
        
        serializer = TransactionSummarySerializer(result, many=True)
        return Response(serializer.data)


class WithdrawalRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for withdrawal requests
    """
    queryset = WithdrawalRequest.objects.select_related('wallet__user').all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return WithdrawalRequestListSerializer
        elif self.action == 'create':
            return WithdrawalRequestCreateSerializer
        elif self.action in ['approve', 'reject']:
            return WithdrawalApprovalSerializer
        return WithdrawalRequestSerializer
    
    def get_permissions(self):
        if self.action in ['approve', 'reject', 'list']:
            return [IsAdminUser()]
        return [IsAuthenticated(), IsWithdrawalOwner()]
    
    def get_queryset(self):
        """Filter withdrawals for current user"""
        if self.request.user.is_staff:
            return self.queryset
        
        wallet = Wallet.objects.filter(user=self.request.user).first()
        if wallet:
            return self.queryset.filter(wallet=wallet)
        return self.queryset.none()
    
    @transaction.atomic
    def perform_create(self, serializer):
        """Create withdrawal request and reserve funds from available balance."""
        wallet, _ = Wallet.objects.select_for_update().get_or_create(user=self.request.user)

        if wallet.is_frozen:
            raise ValidationError({'non_field_errors': ['Wallet is frozen. Withdrawals are disabled.']})

        amount = serializer.validated_data['amount']
        if not WalletService.can_withdraw_amount(wallet, amount):
            withdrawable = WalletService.withdrawable_balance(wallet)
            raise ValidationError({
                'amount': [
                    f'Amount cannot exceed your withdrawable balance of '
                    f'{withdrawable} {wallet.currency}.',
                ],
            })

        from apps.fees.engine import FeeEngine

        method = serializer.validated_data.get('withdrawal_method', '')
        fee_line = FeeEngine.calculate_withdrawal(amount, method)
        withdrawal = serializer.save(
            wallet=wallet,
            processing_fee=fee_line.amount,
            net_amount=amount - fee_line.amount,
        )

        try:
            WalletService.register_pending_withdrawal(wallet, withdrawal)
        except ValueError as exc:
            withdrawal.delete()
            raise ValidationError({'amount': [str(exc)]}) from exc
    
    @action(detail=False, methods=['get'])
    def my_withdrawals(self, request):
        """Get current user's withdrawal requests"""
        wallet = Wallet.objects.filter(user=request.user).first()
        if not wallet:
            return Response([])
        
        withdrawals = self.queryset.filter(wallet=wallet)
        
        # Filter by status
        status_filter = request.query_params.get('status')
        if status_filter:
            withdrawals = withdrawals.filter(status=status_filter)
        
        page = self.paginate_queryset(withdrawals)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(withdrawals, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve withdrawal request (admin only)"""
        withdrawal = self.get_object()

        try:
            if withdrawal.status == 'pending':
                result = WalletService.process_withdrawal(withdrawal, request.user)
            elif withdrawal.status in ('approved', 'processing') and not WalletService.withdrawal_debit_applied(withdrawal):
                result = WalletService.apply_missing_withdrawal_debit(withdrawal, request.user)
            else:
                return Response(
                    {'error': 'Withdrawal cannot be approved in its current state'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(result)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject withdrawal request (admin only)"""
        withdrawal = self.get_object()
        serializer = WithdrawalApprovalSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        if withdrawal.status != 'pending':
            return Response(
                {'error': 'Only pending withdrawals can be rejected'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            if withdrawal.status == 'pending':
                WalletService.release_withdrawal_reservation(withdrawal)
            withdrawal.status = 'rejected'
            withdrawal.rejection_reason = serializer.validated_data['rejection_reason']
            withdrawal.approved_by = request.user
            withdrawal.approved_at = timezone.now()
            withdrawal.save()
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'message': 'Withdrawal request rejected'})
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel withdrawal request"""
        withdrawal = self.get_object()
        
        if withdrawal.status not in ['pending', 'approved']:
            return Response(
                {'error': 'Only pending or approved withdrawals can be cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            if withdrawal.status == 'pending':
                WalletService.release_withdrawal_reservation(withdrawal)
            withdrawal.status = 'cancelled'
            withdrawal.save()
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'message': 'Withdrawal request cancelled'})


class WalletFreezeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for wallet freeze history (read-only)
    """
    queryset = WalletFreeze.objects.select_related('wallet__user', 'frozen_by', 'unfrozen_by').all()
    serializer_class = WalletFreezeSerializer
    permission_classes = [IsAdminUser]


class WalletLimitViewSet(viewsets.ModelViewSet):
    """
    ViewSet for wallet limits
    """
    queryset = WalletLimit.objects.select_related('wallet__user').all()
    serializer_class = WalletLimitSerializer
    permission_classes = [IsAdminUser]
    
    @action(detail=False, methods=['get'])
    def my_limits(self, request):
        """Get current user's wallet limits"""
        wallet = Wallet.objects.filter(user=request.user).first()
        if not wallet:
            return Response([])
        
        limits = self.queryset.filter(wallet=wallet, is_active=True)
        serializer = self.get_serializer(limits, many=True)
        return Response(serializer.data)
