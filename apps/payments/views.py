from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.contenttypes.models import ContentType
from django.db.models import Sum, Count, Q
from django.utils import timezone
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

from .models import Payment, PaymentMethod, Refund, Payout, Transaction
from .serializers import (
    PaymentSerializer, PaymentCreateSerializer, PaymentListSerializer,
    PaymentMethodSerializer, PaymentMethodCreateSerializer,
    RefundSerializer, RefundCreateSerializer,
    PayoutSerializer, PayoutCreateSerializer,
    TransactionSerializer, TransactionListSerializer,
    PaymentStatsSerializer,
    PaymentHistoryResponseSerializer,
    FeePreviewSerializer,
    PlatformFeeSettingsPublicSerializer,
    EscrowReleaseSerializer,
)
from .permissions import IsPaymentParticipant, IsPaymentMethodOwner, IsRefundAuthorized, IsPayoutOwner
from .services import PaymentService
from .gateways.esewa import ESewaGateway
from .gateways.khalti import KhaltiGateway


class PaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing payments
    """
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return PaymentCreateSerializer
        elif self.action == 'list':
            return PaymentListSerializer
        return PaymentSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = Payment.objects.select_related('payer', 'payee', 'content_type')
        
        # Filter by user participation
        queryset = queryset.filter(Q(payer=user) | Q(payee=user))
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by payment type
        type_filter = self.request.query_params.get('type')
        if type_filter:
            queryset = queryset.filter(payment_type=type_filter)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        serializer.save(payer=self.request.user)
    
    @action(detail=False, methods=['get'])
    def my_payments(self, request):
        """Get payments made by current user"""
        payments = self.get_queryset().filter(payer=request.user)
        serializer = self.get_serializer(payments, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def received_payments(self, request):
        """Get payments received by current user"""
        payments = self.get_queryset().filter(payee=request.user)
        serializer = self.get_serializer(payments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def fee_settings(self, request):
        """Public platform fee settings (for offer acceptance UI)."""
        from .fee_service import PlatformFeeService

        payload = PlatformFeeService.public_settings_payload()
        serializer = PlatformFeeSettingsPublicSerializer(payload)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def fee_preview(self, request):
        """Preview fees for a bid amount before accepting an offer."""
        from .fee_service import PlatformFeeService

        amount_raw = request.query_params.get('amount')
        if not amount_raw:
            return Response(
                {'error': 'amount query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            amount = Decimal(str(amount_raw))
        except Exception:
            return Response(
                {'error': 'amount must be a valid number'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment_method = request.query_params.get('payment_method', 'wallet')
        breakdown = PlatformFeeService.calculate_task_payment_fees(
            amount,
            payment_method=payment_method,
        )
        breakdown['currency'] = getattr(settings, 'DEFAULT_CURRENCY', 'NPR')
        serializer = FeePreviewSerializer(breakdown)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def payment_history(self, request):
        """
        Task-related payment history for the tasker dashboard.

        direction=earned — payouts received after completing tasks (payee).
        direction=outgoing — payments made when posting/accepting tasks (payer + escrow holds).
        """
        from apps.tasks.models import Task
        from apps.wallets.models import Wallet, WalletTransaction

        direction = request.query_params.get('direction', 'earned')
        if direction not in ('earned', 'outgoing'):
            return Response(
                {'error': 'direction must be earned or outgoing'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        items = []
        currency = getattr(settings, 'DEFAULT_CURRENCY', 'NPR')

        def task_title_for(content_type, object_id):
            if content_type and content_type.model == 'task' and object_id:
                task = Task.objects.filter(pk=object_id).only('title').first()
                if task:
                    return task.title
            return None

        def is_wallet_recharge_tx(tx):
            meta = tx.metadata or {}
            if meta.get('channel') == 'admin_manual':
                return True
            if meta.get('gateway') == 'esewa':
                return True
            if meta.get('esewa_transaction_uuid'):
                return True
            desc = (tx.description or '').lower()
            return 'wallet recharge' in desc or 'manual wallet recharge' in desc

        if direction == 'earned':
            from .escrow_lifecycle import EscrowLifecycleService

            try:
                EscrowLifecycleService.release_stale_completed_escrows_for_user(user)
            except Exception as exc:
                logger.warning(
                    'Stale escrow sync on payment_history for user %s: %s',
                    user.id,
                    exc,
                )

            payments = Payment.objects.filter(
                payee=user,
                payment_type='task_payment',
                status__in=['released', 'succeeded'],
            ).select_related('content_type').order_by('-created_at')

            for payment in payments:
                title = task_title_for(payment.content_type, payment.object_id)
                if not title:
                    title = payment.description or 'Task payment received'
                gross = payment.amount
                platform_fee = payment.platform_fee or Decimal('0.00')
                net = payment.net_amount if payment.net_amount is not None else payment.amount
                fee_part = (
                    f' · Fee {platform_fee} {payment.currency}'
                    if platform_fee > 0
                    else ''
                )
                items.append({
                    'id': f'payment-{payment.id}',
                    'kind': 'payment',
                    'title': title,
                    'subtitle': f'Task earnings (net){fee_part}',
                    'amount': net,
                    'gross_amount': gross,
                    'platform_fee': platform_fee,
                    'net_amount': net,
                    'currency': payment.currency,
                    'status': payment.status,
                    'direction': 'earned',
                    'created_at': payment.escrow_released_at or payment.completed_at or payment.created_at,
                    'task_id': payment.object_id if payment.content_type and payment.content_type.model == 'task' else None,
                })

            wallet = Wallet.objects.filter(user=user).first()
            if wallet:
                wallet_txs = WalletTransaction.objects.filter(
                    wallet=wallet,
                    status='completed',
                    transaction_type__in=['credit', 'bonus'],
                ).order_by('-created_at')

                payment_ids_in_items = {
                    str(p['id']).replace('payment-', '')
                    for p in items
                    if p['kind'] == 'payment'
                }

                for tx in wallet_txs:
                    if is_wallet_recharge_tx(tx):
                        continue
                    meta = tx.metadata or {}
                    if meta.get('settlement_type') != 'escrow_receive' and not meta.get('payment_id'):
                        if 'payment received' not in (tx.description or '').lower():
                            continue
                    if meta.get('payment_id') and str(meta['payment_id']) in payment_ids_in_items:
                        continue
                    task_id = meta.get('task_id')
                    title = task_title_for(
                        ContentType.objects.get_for_model(Task) if task_id else None,
                        task_id,
                    ) if task_id else None
                    if not title:
                        title = tx.description or 'Task earnings'
                    items.append({
                        'id': f'wallet-{tx.id}',
                        'kind': 'wallet',
                        'title': title,
                        'subtitle': 'Wallet credit',
                        'amount': tx.amount,
                        'currency': tx.currency,
                        'status': tx.status,
                        'direction': 'earned',
                        'created_at': tx.completed_at or tx.created_at,
                        'task_id': task_id,
                    })
        else:
            payments = Payment.objects.filter(
                payer=user,
                payment_type='task_payment',
            ).exclude(status='cancelled').select_related('content_type').order_by('-created_at')

            for payment in payments:
                title = task_title_for(payment.content_type, payment.object_id)
                if not title:
                    title = payment.description or 'Task payment'
                platform_fee = payment.platform_fee or Decimal('0.00')
                net = payment.net_amount if payment.net_amount is not None else payment.amount
                fee_hint = (
                    f' · Tasker receives {net} {payment.currency}'
                    if platform_fee > 0
                    else ''
                )
                items.append({
                    'id': f'payment-{payment.id}',
                    'kind': 'payment',
                    'title': title,
                    'subtitle': f'Posted task payment (escrow){fee_hint}',
                    'amount': payment.amount,
                    'gross_amount': payment.amount,
                    'platform_fee': platform_fee,
                    'net_amount': net,
                    'currency': payment.currency,
                    'status': payment.status,
                    'direction': 'outgoing',
                    'created_at': payment.created_at,
                    'task_id': payment.object_id if payment.content_type and payment.content_type.model == 'task' else None,
                })

            wallet = Wallet.objects.filter(user=user).first()
            if wallet:
                wallet_txs = WalletTransaction.objects.filter(
                    wallet=wallet,
                    status='completed',
                    transaction_type__in=['hold', 'debit'],
                ).order_by('-created_at')

                payment_ids_in_items = {
                    str(p['id']).replace('payment-', '')
                    for p in items
                    if p['kind'] == 'payment'
                }

                for tx in wallet_txs:
                    meta = tx.metadata or {}
                    if tx.transaction_type == 'debit' and meta.get('withdrawal_id'):
                        items.append({
                            'id': f'wallet-{tx.id}',
                            'kind': 'wallet',
                            'title': tx.description or 'Withdrawal',
                            'subtitle': 'Withdrawal',
                            'amount': tx.amount,
                            'currency': tx.currency,
                            'status': tx.status,
                            'direction': 'outgoing',
                            'created_at': tx.completed_at or tx.created_at,
                            'task_id': None,
                        })
                        continue
                    if tx.transaction_type == 'hold':
                        if meta.get('payment_id') and str(meta['payment_id']) in payment_ids_in_items:
                            continue
                    elif tx.transaction_type == 'debit':
                        if meta.get('settlement_type') != 'escrow_payout' and meta.get('type') != 'escrow':
                            if 'escrow' not in (tx.description or '').lower():
                                continue
                    task_id = meta.get('task_id')
                    title = None
                    if task_id:
                        title = task_title_for(
                            ContentType.objects.get_for_model(Task),
                            task_id,
                        )
                    if not title:
                        title = tx.description or 'Task payment'
                    items.append({
                        'id': f'wallet-{tx.id}',
                        'kind': 'wallet',
                        'title': title,
                        'subtitle': 'Escrow hold' if tx.transaction_type == 'hold' else 'Payment sent',
                        'amount': tx.amount,
                        'currency': tx.currency,
                        'status': tx.status,
                        'direction': 'outgoing',
                        'created_at': tx.completed_at or tx.created_at,
                        'task_id': task_id,
                    })

        items.sort(key=lambda row: row['created_at'], reverse=True)

        seen = set()
        deduped = []
        for row in items:
            key = (row['kind'], row['id'])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
            if row.get('currency'):
                currency = row['currency']

        total_amount = sum((row['amount'] for row in deduped), Decimal('0.00'))

        payload = {
            'direction': direction,
            'items': deduped,
            'total_amount': total_amount,
            'count': len(deduped),
            'currency': currency,
        }
        serializer = PaymentHistoryResponseSerializer(payload)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get payment statistics for current user"""
        user = request.user
        
        # Payments made
        payments_made = Payment.objects.filter(payer=user)
        total_paid = payments_made.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Payments received
        payments_received = Payment.objects.filter(payee=user)
        total_received = payments_received.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Fees paid
        total_fees = payments_made.aggregate(
            total=Sum('platform_fee') + Sum('payment_processing_fee')
        )['total'] or Decimal('0.00')
        
        # Net earnings
        net_earnings = payments_received.aggregate(total=Sum('net_amount'))['total'] or Decimal('0.00')
        
        stats = {
            'total_payments': payments_made.count(),
            'total_amount': total_paid,
            'successful_payments': payments_made.filter(status='succeeded').count(),
            'failed_payments': payments_made.filter(status='failed').count(),
            'pending_payments': payments_made.filter(status='pending').count(),
            'total_refunds': payments_made.aggregate(total=Sum('refund_amount'))['total'] or Decimal('0.00'),
            'total_fees': total_fees,
            'net_earnings': net_earnings,
        }
        
        serializer = PaymentStatsSerializer(stats)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        """Process a pending payment"""
        payment = self.get_object()
        
        if payment.status != 'pending':
            return Response(
                {'error': 'Payment is not in pending status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            result = PaymentService.process_payment(payment)
            return Response(result)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def release_escrow(self, request, pk=None):
        """Release payment from escrow"""
        payment = self.get_object()
        serializer = EscrowReleaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            result = PaymentService.release_escrow(
                payment,
                release_immediately=serializer.validated_data.get('release_immediately', False),
                scheduled_date=serializer.validated_data.get('scheduled_release_date')
            )
            return Response(result)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'], url_path='esewa/initiate')
    def esewa_initiate(self, request):
        """Initiate eSewa payment"""
        try:
            # Get request data
            amount = request.data.get('amount')
            transaction_id = request.data.get('transaction_id')
            product_name = request.data.get('product_name', 'Wallet Recharge')
            success_url = request.data.get('success_url')
            failure_url = request.data.get('failure_url')
            
            # Validate required fields
            if not all([amount, transaction_id, success_url, failure_url]):
                return Response(
                    {'error': 'Missing required fields: amount, transaction_id, success_url, failure_url'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Initialize eSewa gateway
            esewa = ESewaGateway()
            
            # Initiate payment
            result = esewa.initiate_payment(
                amount=Decimal(str(amount)),
                transaction_id=transaction_id,
                product_name=product_name,
                customer_info={'user_id': request.user.id},
                success_url=success_url,
                failure_url=failure_url
            )
            
            if result.get('success'):
                return Response({
                    'success': True,
                    'payment_url': result['payment_url'],
                    'form_data': result['form_data'],
                    'transaction_id': result['transaction_id']
                })
            else:
                return Response(
                    {'error': result.get('error', 'Payment initiation failed')},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"eSewa initiation error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'], url_path='esewa/verify')
    def esewa_verify(self, request):
        """Verify eSewa payment using status check API"""
        try:
            # Get request data
            transaction_id = request.data.get('transaction_uuid') or request.data.get('transaction_id')
            amount = request.data.get('total_amount') or request.data.get('amount')
            
            # Validate required fields
            if not all([transaction_id, amount]):
                return Response(
                    {'error': 'Missing required fields: transaction_uuid (or transaction_id) and total_amount (or amount)'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Initialize eSewa gateway
            esewa = ESewaGateway()
            
            # Verify payment using status check API
            result = esewa.verify_payment(
                transaction_id=transaction_id,
                amount=Decimal(str(amount))
            )
            
            logger.info(f"eSewa verification result: {result}")
            
            if result.get('verified'):
                # Credit user's wallet (idempotent per transaction_uuid)
                from apps.wallets.models import Wallet, WalletTransaction
                from apps.wallets.services import WalletService

                wallet, _ = Wallet.objects.get_or_create(user=request.user)
                amount_dec = Decimal(str(amount))

                already_credited = WalletTransaction.objects.filter(
                    wallet=wallet,
                    transaction_type='credit',
                    status='completed',
                    metadata__esewa_transaction_uuid=str(transaction_id),
                ).exists()

                if not already_credited:
                    WalletService.credit_wallet(
                        wallet,
                        amount_dec,
                        description="Wallet recharge via eSewa",
                        transaction_type='credit',
                        metadata={
                            'gateway': 'esewa',
                            'esewa_transaction_uuid': str(transaction_id),
                            'esewa_ref_id': result.get('reference_id'),
                            'esewa_status': (result.get('raw_response') or {}).get('status'),
                        },
                    )
                
                return Response({
                    'success': True,
                    'verified': True,
                    'transaction_id': result['transaction_id'],
                    'reference_id': result.get('reference_id'),
                    'status': result['status'],
                    'wallet_credited': not already_credited,
                })
            else:
                return Response(
                    {
                        'success': False,
                        'verified': False,
                        'error': result.get('error', 'Payment verification failed'),
                        'status': result.get('status', 'failed')
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"eSewa verification error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'], url_path='khalti/initiate')
    def khalti_initiate(self, request):
        """Initiate Khalti payment"""
        try:
            # Get request data
            amount = request.data.get('amount')
            transaction_id = request.data.get('transaction_id')
            product_name = request.data.get('product_name', 'Wallet Recharge')
            customer_info = request.data.get('customer_info', {})
            success_url = request.data.get('success_url')
            failure_url = request.data.get('failure_url')
            
            # Validate required fields
            if not all([amount, transaction_id, success_url, failure_url]):
                return Response(
                    {'error': 'Missing required fields: amount, transaction_id, success_url, failure_url'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Initialize Khalti gateway
            khalti = KhaltiGateway()
            
            # Initiate payment
            result = khalti.initiate_payment(
                amount=Decimal(str(amount)),
                transaction_id=transaction_id,
                product_name=product_name,
                customer_info=customer_info,
                success_url=success_url,
                failure_url=failure_url
            )
            
            if result.get('success'):
                return Response({
                    'success': True,
                    'payment_url': result['payment_url'],
                    'pidx': result.get('pidx'),
                    'transaction_id': result['transaction_id'],
                    'expires_at': result.get('expires_at')
                })
            else:
                return Response(
                    {'error': result.get('error', 'Payment initiation failed')},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"Khalti initiation error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'], url_path='khalti/verify')
    def khalti_verify(self, request):
        """Verify Khalti payment"""
        try:
            # Get request data
            transaction_id = request.data.get('transaction_id')
            pidx = request.data.get('pidx')
            
            # Validate required fields
            if not all([transaction_id, pidx]):
                return Response(
                    {'error': 'Missing required fields: transaction_id, pidx'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Initialize Khalti gateway
            khalti = KhaltiGateway()
            
            # Verify payment
            result = khalti.verify_payment(
                transaction_id=transaction_id,
                pidx=pidx
            )
            
            if result.get('verified'):
                from decimal import Decimal
                from apps.wallets.models import Wallet, WalletTransaction
                from apps.wallets.services import WalletService

                wallet, _ = Wallet.objects.get_or_create(user=request.user)
                amount_dec = Decimal(str(result.get('amount', 0)))

                already_credited = WalletTransaction.objects.filter(
                    wallet=wallet,
                    transaction_type='credit',
                    status='completed',
                    metadata__khalti_transaction_id=str(transaction_id),
                ).exists()

                if amount_dec > 0 and not already_credited:
                    WalletService.credit_wallet(
                        wallet,
                        amount_dec,
                        description='Wallet recharge via Khalti',
                        transaction_type='credit',
                        metadata={
                            'gateway': 'khalti',
                            'khalti_transaction_id': str(transaction_id),
                            'khalti_pidx': pidx,
                        },
                    )

                return Response({
                    'success': True,
                    'verified': True,
                    'transaction_id': result['transaction_id'],
                    'amount': result.get('amount'),
                    'status': result['status'],
                    'wallet_credited': not already_credited,
                })
            else:
                return Response(
                    {'error': result.get('error', 'Payment verification failed')},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"Khalti verification error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PaymentMethodViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing payment methods
    """
    permission_classes = [IsAuthenticated, IsPaymentMethodOwner]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return PaymentMethodCreateSerializer
        return PaymentMethodSerializer
    
    def get_queryset(self):
        return PaymentMethod.objects.filter(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        """Create a linked payment method (eSewa or bank account)."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        method_type = serializer.validated_data['method_type']

        try:
            if method_type == 'esewa':
                payment_method = PaymentMethod.objects.create(
                    user=request.user,
                    method_type='esewa',
                    esewa_account_name=serializer.validated_data['esewa_account_name'],
                    esewa_phone_number=serializer.validated_data['esewa_phone_number'],
                    is_default=serializer.validated_data.get('is_default', False),
                    is_verified=True,
                )
            elif method_type == 'bank_account':
                payment_method = PaymentMethod.objects.create(
                    user=request.user,
                    method_type='bank_account',
                    bank_name=serializer.validated_data.get('bank_name', ''),
                    account_last4=serializer.validated_data.get('account_last4', '')[-4:]
                    if serializer.validated_data.get('account_last4')
                    else '',
                    is_default=serializer.validated_data.get('is_default', False),
                    is_verified=False,
                )
            else:
                return Response(
                    {'error': 'Only eSewa and bank account methods are supported.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not request.user.has_payment_method:
                request.user.has_payment_method = True
                request.user.save(update_fields=['has_payment_method'])

            output_serializer = PaymentMethodSerializer(payment_method)
            return Response(output_serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Failed to create payment method: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set payment method as default"""
        payment_method = self.get_object()
        payment_method.is_default = True
        payment_method.save()
        
        serializer = self.get_serializer(payment_method)
        return Response(serializer.data)
    
class RefundViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing refunds
    """
    permission_classes = [IsAuthenticated, IsRefundAuthorized]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return RefundCreateSerializer
        return RefundSerializer
    
    def get_queryset(self):
        user = self.request.user
        return Refund.objects.filter(
            Q(payment__payer=user) | Q(payment__payee=user)
        ).select_related('payment', 'initiated_by')
    
    def perform_create(self, serializer):
        refund = serializer.save(initiated_by=self.request.user)
        
        try:
            PaymentService.process_refund(refund)
        except Exception as e:
            refund.status = 'failed'
            refund.failure_reason = str(e)
            refund.save()
            raise


class PayoutViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing payouts
    """
    permission_classes = [IsAuthenticated, IsPayoutOwner]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return PayoutCreateSerializer
        return PayoutSerializer
    
    def get_queryset(self):
        return Payout.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        payout = serializer.save(user=self.request.user)
        
        # Process payout
        try:
            PaymentService.process_payout(payout)
        except Exception as e:
            payout.status = 'failed'
            payout.failure_reason = str(e)
            payout.save()
            raise
    
    @action(detail=False, methods=['get'])
    def available_balance(self, request):
        """Get available balance for payout"""
        user = request.user
        return Response({
            'available_balance': user.wallet_balance,
            'currency': 'NPR',
            'minimum_payout': Decimal('10.00')
        })


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing transaction history (read-only)
    """
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return TransactionListSerializer
        return TransactionSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = Transaction.objects.filter(user=user)
        
        # Filter by transaction type
        type_filter = self.request.query_params.get('type')
        if type_filter:
            queryset = queryset.filter(transaction_type=type_filter)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        return queryset.order_by('-created_at')
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get transaction summary"""
        user = request.user
        transactions = self.get_queryset()
        
        summary = {
            'total_transactions': transactions.count(),
            'current_balance': user.wallet_balance,
            'total_credits': transactions.filter(amount__gt=0).aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00'),
            'total_debits': transactions.filter(amount__lt=0).aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00'),
        }
        
        return Response(summary)


