from rest_framework import serializers
from .models import Payment, PaymentMethod, Refund, Payout, Transaction
from apps.users.serializers import UserListSerializer


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model"""
    
    payer_details = UserListSerializer(source='payer', read_only=True)
    payee_details = UserListSerializer(source='payee', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'payer', 'payer_details', 'payee', 'payee_details',
            'content_type', 'object_id', 'amount', 'currency',
            'payment_type', 'payment_method', 'status',
            'platform_fee', 'payment_processing_fee', 'net_amount',
            'is_escrowed', 'escrow_released_at', 'escrow_release_scheduled_at',
            'refund_amount', 'refund_reason', 'refunded_at',
            'description', 'metadata', 'failure_reason',
            'created_at', 'updated_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'payer_details', 'payee_details', 'net_amount',
            'refund_amount', 'refunded_at', 'created_at', 'updated_at', 'completed_at'
        ]


class PaymentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating payments"""
    
    class Meta:
        model = Payment
        fields = [
            'payee', 'content_type', 'object_id', 'amount', 'currency',
            'payment_type', 'payment_method', 'description', 'metadata'
        ]
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value


class PaymentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for payment lists"""
    
    payer_name = serializers.CharField(source='payer.get_full_name', read_only=True)
    payee_name = serializers.CharField(source='payee.get_full_name', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'payer', 'payer_name', 'payee', 'payee_name',
            'amount', 'currency', 'payment_type', 'payment_method',
            'status', 'net_amount', 'is_escrowed', 'created_at'
        ]


class PaymentMethodSerializer(serializers.ModelSerializer):
    """Serializer for PaymentMethod model"""
    
    # Add computed fields for frontend compatibility
    last_four = serializers.SerializerMethodField()
    expiry_date = serializers.SerializerMethodField()
    
    class Meta:
        model = PaymentMethod
        fields = [
            'id', 'user', 'method_type', 'is_default', 'is_verified',
            'card_brand', 'card_last4', 'card_exp_month', 'card_exp_year',
            'bank_name', 'account_last4', 
            'esewa_account_name', 'esewa_phone_number',
            'billing_details',
            'last_four', 'expiry_date',  # Frontend-compatible fields
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'is_verified', 'card_brand', 'card_last4',
            'card_exp_month', 'card_exp_year', 'bank_name', 'account_last4',
            'last_four', 'expiry_date',
            'created_at', 'updated_at'
        ]
    
    def get_last_four(self, obj):
        """Get last 4 digits for frontend"""
        if obj.method_type == 'card':
            return obj.card_last4
        elif obj.method_type == 'bank_account':
            return obj.account_last4
        return None
    
    def get_expiry_date(self, obj):
        """Get expiry date in MM/YY format for frontend"""
        if obj.method_type == 'card' and obj.card_exp_month and obj.card_exp_year:
            return f"{obj.card_exp_month:02d}/{str(obj.card_exp_year)[-2:]}"
        return None


class PaymentMethodCreateSerializer(serializers.Serializer):
    """Serializer for creating linked payment methods (eSewa or bank account)."""

    method_type = serializers.ChoiceField(choices=['bank_account', 'esewa'], required=True)
    is_default = serializers.BooleanField(default=False)

    esewa_account_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    esewa_phone_number = serializers.CharField(required=False, allow_blank=True, max_length=15)

    bank_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    account_last4 = serializers.CharField(required=False, allow_blank=True, max_length=4)

    def validate_esewa_phone_number(self, value):
        if value:
            # Remove any spaces or dashes
            cleaned = value.replace(' ', '').replace('-', '')
            
            # Check if it's 10 digits and starts with 97 or 98
            if not cleaned.isdigit():
                raise serializers.ValidationError("Phone number must contain only digits")
            
            if len(cleaned) != 10:
                raise serializers.ValidationError("Phone number must be exactly 10 digits")
            
            if not (cleaned.startswith('98') or cleaned.startswith('97')):
                raise serializers.ValidationError("eSewa phone number must start with 97 or 98")
            
            return cleaned
        return value
    
    def validate(self, data):
        method_type = data.get('method_type')
        
        if method_type == 'esewa':
            if not data.get('esewa_account_name'):
                raise serializers.ValidationError({
                    'esewa_account_name': 'Account name is required for eSewa'
                })
            if not data.get('esewa_phone_number'):
                raise serializers.ValidationError({
                    'esewa_phone_number': 'Phone number is required for eSewa'
                })
        elif method_type == 'bank_account':
            if not data.get('bank_name'):
                raise serializers.ValidationError({
                    'bank_name': 'Bank name is required for bank account'
                })

        return data


class RefundSerializer(serializers.ModelSerializer):
    """Serializer for Refund model"""
    
    payment_details = PaymentListSerializer(source='payment', read_only=True)
    initiated_by_name = serializers.CharField(source='initiated_by.get_full_name', read_only=True)
    
    class Meta:
        model = Refund
        fields = [
            'id', 'payment', 'payment_details', 'amount', 'currency',
            'reason', 'description', 'status', 'initiated_by',
            'initiated_by_name', 'failure_reason', 'metadata',
            'created_at', 'updated_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'payment_details', 'initiated_by_name', 'status',
            'failure_reason', 'created_at', 'updated_at', 'completed_at'
        ]


class RefundCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating refunds"""
    
    class Meta:
        model = Refund
        fields = ['payment', 'amount', 'reason', 'description']
    
    def validate(self, data):
        payment = data['payment']
        amount = data['amount']
        
        # Check if payment can be refunded
        if payment.status not in ['succeeded', 'partially_refunded']:
            raise serializers.ValidationError("Payment cannot be refunded")
        
        # Check refund amount
        max_refundable = payment.amount - payment.refund_amount
        if amount > max_refundable:
            raise serializers.ValidationError(
                f"Refund amount cannot exceed {max_refundable} {payment.currency}"
            )
        
        return data


class PayoutSerializer(serializers.ModelSerializer):
    """Serializer for Payout model"""
    
    user_details = UserListSerializer(source='user', read_only=True)
    
    class Meta:
        model = Payout
        fields = [
            'id', 'user', 'user_details', 'amount', 'currency',
            'payout_method', 'status', 'processing_fee', 'net_amount',
            'description', 'failure_reason', 'metadata',
            'created_at', 'updated_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'user_details', 'status', 'processing_fee', 'net_amount',
            'failure_reason', 'created_at', 'updated_at', 'completed_at'
        ]


class PayoutCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating payouts"""
    
    class Meta:
        model = Payout
        fields = ['amount', 'currency', 'payout_method', 'description']
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        
        # Check minimum payout amount
        if value < 10:
            raise serializers.ValidationError("Minimum payout amount is 10.00")
        
        return value
    
    def validate(self, data):
        user = self.context['request'].user
        amount = data['amount']
        
        # Check if user has sufficient balance
        if user.wallet_balance < amount:
            raise serializers.ValidationError(
                f"Insufficient balance. Available: {user.wallet_balance}"
            )
        
        return data


class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for Transaction model"""
    
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = Transaction
        fields = [
            'id', 'user', 'user_name', 'transaction_type', 'amount',
            'currency', 'balance_before', 'balance_after', 'payment',
            'refund', 'payout', 'description', 'metadata', 'created_at'
        ]
        read_only_fields = '__all__'


class TransactionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for transaction lists"""
    
    class Meta:
        model = Transaction
        fields = [
            'id', 'transaction_type', 'amount', 'currency',
            'balance_after', 'description', 'created_at'
        ]


class FeePreviewSerializer(serializers.Serializer):
    """Fee breakdown preview for a task bid amount."""

    gross_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    platform_fee = serializers.DecimalField(max_digits=10, decimal_places=2)
    processing_fee = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_fees = serializers.DecimalField(max_digits=10, decimal_places=2)
    net_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    poster_total_held = serializers.DecimalField(max_digits=10, decimal_places=2)
    tasker_commission_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    fees_enabled = serializers.BooleanField()
    currency = serializers.CharField()


class PlatformFeeSettingsPublicSerializer(serializers.Serializer):
    """Public read-only fee settings for clients."""

    is_enabled = serializers.BooleanField()
    tasker_commission_percent = serializers.CharField()
    poster_service_fee_percent = serializers.CharField()
    min_platform_fee = serializers.CharField()
    max_platform_fee = serializers.CharField(allow_null=True)
    currency = serializers.CharField()


class PaymentHistoryItemSerializer(serializers.Serializer):
    """Unified payment / wallet activity for tasker dashboard history."""

    id = serializers.CharField()
    kind = serializers.ChoiceField(choices=['payment', 'wallet'])
    title = serializers.CharField()
    subtitle = serializers.CharField(allow_blank=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    gross_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )
    platform_fee = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )
    net_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )
    currency = serializers.CharField()
    status = serializers.CharField()
    direction = serializers.ChoiceField(choices=['earned', 'outgoing'])
    created_at = serializers.DateTimeField()
    task_id = serializers.UUIDField(required=False, allow_null=True)


class PaymentHistoryResponseSerializer(serializers.Serializer):
    """Payment history tab response."""

    direction = serializers.ChoiceField(choices=['earned', 'outgoing'])
    items = PaymentHistoryItemSerializer(many=True)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    count = serializers.IntegerField()
    currency = serializers.CharField()


class PaymentStatsSerializer(serializers.Serializer):
    """Serializer for payment statistics"""
    
    total_payments = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    successful_payments = serializers.IntegerField()
    failed_payments = serializers.IntegerField()
    pending_payments = serializers.IntegerField()
    total_refunds = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_fees = serializers.DecimalField(max_digits=10, decimal_places=2)
    net_earnings = serializers.DecimalField(max_digits=10, decimal_places=2)


class EscrowReleaseSerializer(serializers.Serializer):
    """Serializer for releasing escrow"""
    
    payment_id = serializers.UUIDField(required=True)
    release_immediately = serializers.BooleanField(default=False)
    scheduled_release_date = serializers.DateTimeField(required=False)
    
    def validate(self, data):
        if not data.get('release_immediately') and not data.get('scheduled_release_date'):
            raise serializers.ValidationError(
                "Either release_immediately or scheduled_release_date must be provided"
            )
        return data


