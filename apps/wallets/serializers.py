from decimal import Decimal

from rest_framework import serializers
from .models import Wallet, WalletTransaction, WithdrawalRequest, WalletFreeze, WalletLimit
from apps.users.serializers import UserListSerializer


class WalletSerializer(serializers.ModelSerializer):
    """Wallet serializer with all details"""
    user = UserListSerializer(read_only=True)
    total_balance = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    can_withdraw_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = Wallet
        fields = [
            'id', 'user', 'available_balance', 'pending_balance', 'held_balance',
            'total_balance', 'total_earned', 'total_withdrawn', 'currency',
            'is_active', 'is_frozen', 'frozen_reason', 'frozen_at',
            'can_withdraw_amount', 'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'available_balance', 'pending_balance', 'held_balance',
            'total_earned', 'total_withdrawn', 'is_frozen', 'frozen_reason',
            'frozen_at', 'created_at', 'updated_at'
        ]
    
    def get_can_withdraw_amount(self, obj):
        """Get maximum withdrawable amount"""
        return obj.available_balance if not obj.is_frozen else 0


class WalletBalanceSerializer(serializers.ModelSerializer):
    """Simplified wallet balance serializer"""
    total_balance = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    recharge_balance = serializers.SerializerMethodField()
    earned_balance = serializers.SerializerMethodField()
    withdrawable_balance = serializers.SerializerMethodField()
    pending_withdrawals_amount = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = [
            'id', 'user_email', 'available_balance', 'pending_balance', 'held_balance',
            'total_balance', 'recharge_balance', 'earned_balance', 'total_earned',
            'withdrawable_balance', 'pending_withdrawals_amount',
            'currency', 'is_frozen'
        ]
        read_only_fields = fields

    def get_withdrawable_balance(self, obj):
        from .services import WalletService

        return WalletService.withdrawable_balance(obj)

    def get_pending_withdrawals_amount(self, obj):
        from .services import WalletService

        return WalletService.pending_withdrawal_total(obj)

    def _breakdown(self, obj):
        cache = getattr(self, '_breakdown_cache', None)
        if cache is None:
            cache = {}
            self._breakdown_cache = cache
        if obj.pk not in cache:
            from .utils import compute_wallet_breakdown

            cache[obj.pk] = compute_wallet_breakdown(obj)
        return cache[obj.pk]

    def get_recharge_balance(self, obj):
        recharge, _ = self._breakdown(obj)
        return recharge

    def get_earned_balance(self, obj):
        _, earned = self._breakdown(obj)
        return earned


class WalletTransactionSerializer(serializers.ModelSerializer):
    """Wallet transaction serializer"""
    wallet_user = serializers.CharField(source='wallet.user.email', read_only=True)
    
    class Meta:
        model = WalletTransaction
        fields = [
            'id', 'wallet', 'wallet_user', 'transaction_type', 'amount', 'currency',
            'status', 'balance_before', 'balance_after', 'description', 'notes',
            'reference_number', 'metadata', 'created_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'wallet_user', 'balance_before', 'balance_after',
            'reference_number', 'created_at', 'completed_at'
        ]


class WalletTransactionListSerializer(serializers.ModelSerializer):
    """Simplified transaction list serializer"""
    
    class Meta:
        model = WalletTransaction
        fields = [
            'id', 'transaction_type', 'amount', 'currency', 'status',
            'description', 'reference_number', 'created_at'
        ]
        read_only_fields = fields


class WalletTransactionCreateSerializer(serializers.ModelSerializer):
    """Create wallet transaction"""
    
    class Meta:
        model = WalletTransaction
        fields = [
            'wallet', 'transaction_type', 'amount', 'currency', 'description',
            'notes', 'metadata'
        ]
    
    def validate_amount(self, value):
        """Validate amount is positive"""
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value


class WithdrawalRequestSerializer(serializers.ModelSerializer):
    """Withdrawal request serializer"""
    wallet_user = serializers.CharField(source='wallet.user.email', read_only=True)
    approved_by_email = serializers.CharField(source='approved_by.email', read_only=True)
    
    class Meta:
        model = WithdrawalRequest
        fields = [
            'id', 'wallet', 'wallet_user', 'amount', 'currency', 'processing_fee',
            'net_amount', 'withdrawal_method', 'bank_account_name', 'bank_account_number',
            'bank_name', 'bank_routing_number', 'status',
            'approved_by', 'approved_by_email', 'approved_at', 'rejection_reason',
            'failure_reason', 'payment_reference', 'notes',
            'metadata', 'created_at', 'updated_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'wallet_user', 'processing_fee', 'net_amount', 'status',
            'approved_by', 'approved_by_email', 'approved_at', 'rejection_reason',
            'failure_reason', 'payment_reference',
            'created_at', 'updated_at', 'completed_at'
        ]


class WithdrawalRequestCreateSerializer(serializers.ModelSerializer):
    """Create withdrawal request"""
    
    class Meta:
        model = WithdrawalRequest
        fields = [
            'amount', 'withdrawal_method', 'bank_account_name', 'bank_account_number',
            'bank_name', 'bank_routing_number', 'notes'
        ]
    
    def validate_amount(self, value):
        """Validate withdrawal amount against wallet available balance."""
        # Admin-configured min/max (stored in rules)
        min_amt = Decimal('10')
        max_amt = None
        try:
            from apps.rules.models import RuleCategory
            from apps.rules.policy_store import get_active_policy_parameters

            params = get_active_policy_parameters(RuleCategory.WITHDRAWAL, 'withdrawal_amount_limits')
            if params.get('min_withdrawal_amount_npr') is not None:
                min_amt = Decimal(str(params['min_withdrawal_amount_npr']))
            if params.get('max_withdrawal_amount_npr') is not None:
                max_amt = Decimal(str(params['max_withdrawal_amount_npr']))
        except Exception:
            pass

        if value < min_amt:
            raise serializers.ValidationError(f'Minimum withdrawal amount is {min_amt} NPR.')
        if max_amt is not None and value > max_amt:
            raise serializers.ValidationError(f'Maximum withdrawal amount is {max_amt} NPR.')

        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return value

        wallet = Wallet.objects.filter(user=request.user).first()
        if not wallet:
            raise serializers.ValidationError('Wallet not found.')
        if wallet.is_frozen:
            raise serializers.ValidationError('Wallet is frozen. Withdrawals are disabled.')

        from .services import WalletService

        withdrawable = WalletService.withdrawable_balance(wallet)
        if value > withdrawable:
            raise serializers.ValidationError(
                f'Amount cannot exceed your withdrawable balance of {withdrawable} {wallet.currency}. '
                f'(Other pending withdrawal requests reduce what you can request now.)'
            )
        return value
    
    def validate(self, data):
        """Validate withdrawal method details"""
        method = data.get('withdrawal_method')
        
        if method == 'bank_transfer':
            required_fields = ['bank_account_name', 'bank_account_number', 'bank_name']
            for field in required_fields:
                if not data.get(field):
                    raise serializers.ValidationError(f"{field} is required for bank transfer")
        
        elif method == 'esewa':
            phone = (data.get('bank_account_number') or '').strip()
            if not phone:
                raise serializers.ValidationError("eSewa phone number is required")
            if not data.get('bank_account_name'):
                raise serializers.ValidationError("eSewa account name is required")

        elif method == 'khalti':
            phone = (data.get('bank_account_number') or '').strip()
            if not phone:
                raise serializers.ValidationError("Khalti phone number is required")
        
        return data


class WithdrawalRequestListSerializer(serializers.ModelSerializer):
    """Simplified withdrawal request list"""
    
    class Meta:
        model = WithdrawalRequest
        fields = [
            'id', 'amount', 'currency', 'net_amount', 'withdrawal_method',
            'status', 'created_at', 'completed_at'
        ]
        read_only_fields = fields


class WithdrawalApprovalSerializer(serializers.Serializer):
    """Approve/reject withdrawal request"""
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    notes = serializers.CharField(required=False, allow_blank=True)
    rejection_reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate rejection reason if rejecting"""
        if data['action'] == 'reject' and not data.get('rejection_reason'):
            raise serializers.ValidationError("Rejection reason is required when rejecting")
        return data


class WalletFreezeSerializer(serializers.ModelSerializer):
    """Wallet freeze serializer"""
    wallet_user = serializers.CharField(source='wallet.user.email', read_only=True)
    frozen_by_email = serializers.CharField(source='frozen_by.email', read_only=True)
    unfrozen_by_email = serializers.CharField(source='unfrozen_by.email', read_only=True)
    
    class Meta:
        model = WalletFreeze
        fields = [
            'id', 'wallet', 'wallet_user', 'reason', 'description',
            'frozen_by', 'frozen_by_email', 'unfrozen_by', 'unfrozen_by_email',
            'is_active', 'frozen_at', 'unfrozen_at'
        ]
        read_only_fields = [
            'id', 'wallet_user', 'frozen_by', 'frozen_by_email',
            'unfrozen_by', 'unfrozen_by_email', 'frozen_at', 'unfrozen_at'
        ]


class WalletFreezeCreateSerializer(serializers.ModelSerializer):
    """Create wallet freeze"""
    
    class Meta:
        model = WalletFreeze
        fields = ['wallet', 'reason', 'description']


class WalletLimitSerializer(serializers.ModelSerializer):
    """Wallet limit serializer"""
    wallet_user = serializers.CharField(source='wallet.user.email', read_only=True)
    
    class Meta:
        model = WalletLimit
        fields = [
            'id', 'wallet', 'wallet_user', 'limit_type', 'amount', 'currency',
            'is_active', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'wallet_user', 'created_at', 'updated_at']


class WalletStatsSerializer(serializers.Serializer):
    """Wallet statistics"""
    total_balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    available_balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    pending_balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    held_balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_earned = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_withdrawn = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_transactions = serializers.IntegerField()
    pending_withdrawals = serializers.IntegerField()
    pending_withdrawals_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()


class TransactionSummarySerializer(serializers.Serializer):
    """Transaction summary by type"""
    transaction_type = serializers.CharField()
    count = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()
