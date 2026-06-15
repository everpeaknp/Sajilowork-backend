from django.db import transaction
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from decimal import Decimal
import logging

from .models import Payment, Refund, Payout, PaymentMethod
from apps.wallets.models import Wallet, WalletTransaction

logger = logging.getLogger(__name__)


class PaymentService:
    """
    Payment processing and business logic (wallet, eSewa, Khalti — no Stripe/PayPal).
    """

    PLATFORM_FEE_PERCENTAGE = Decimal('0.15')

    @staticmethod
    def calculate_fees(amount, payment_method: str = 'wallet'):
        """Calculate fees from FeeRule engine."""
        from apps.fees.engine import FeeContext, FeeEngine

        ctx = FeeContext(payment_method=payment_method)
        breakdown = FeeEngine.calculate_task_settlement(Decimal(str(amount)), ctx)
        processing_fee = Decimal('0.00')
        if payment_method not in ('wallet',):
            processing_fee = breakdown.get('processing_fee', Decimal('0.00'))

        net = breakdown['worker_receives'] - processing_fee
        if net < 0:
            net = Decimal('0.00')

        return {
            'platform_fee': breakdown['platform_fee'],
            'payment_processing_fee': processing_fee,
            'net_amount': net,
        }

    @staticmethod
    @transaction.atomic
    def process_payment(payment):
        """Mark a wallet-funded payment as succeeded and update balances."""
        from .models import Transaction

        try:
            fees = PaymentService.calculate_fees(
                payment.amount,
                payment_method=payment.payment_method or 'wallet',
            )
            payment.platform_fee = fees['platform_fee']
            payment.payment_processing_fee = fees['payment_processing_fee']
            payment.net_amount = fees['net_amount']
            payment.status = 'succeeded'
            payment.completed_at = timezone.now()

            if payment.payee:
                payment.payee.wallet_balance += payment.net_amount
                payment.payee.save(update_fields=['wallet_balance'])

            Transaction.objects.create(
                user=payment.payer,
                transaction_type='payment',
                amount=-payment.amount,
                currency=payment.currency,
                balance_before=payment.payer.wallet_balance,
                balance_after=payment.payer.wallet_balance,
                payment=payment,
                description=f"Payment for {payment.description}",
            )

            if payment.payee:
                Transaction.objects.create(
                    user=payment.payee,
                    transaction_type='payment',
                    amount=payment.net_amount,
                    currency=payment.currency,
                    balance_before=payment.payee.wallet_balance - payment.net_amount,
                    balance_after=payment.payee.wallet_balance,
                    payment=payment,
                    description=f"Payment received for {payment.description}",
                )

            payment.save()

            return {
                'success': True,
                'payment_id': str(payment.id),
                'status': payment.status,
                'amount': str(payment.amount),
                'net_amount': str(payment.net_amount),
            }
        except Exception as e:
            payment.status = 'failed'
            payment.failure_reason = str(e)
            payment.save()
            logger.error(f"Error processing payment {payment.id}: {e}")
            raise

    @staticmethod
    @transaction.atomic
    def process_refund(refund):
        """Process a refund (wallet reversal; external gateways handled separately)."""
        from .models import Transaction

        try:
            payment = refund.payment
            refund.status = 'succeeded'
            refund.completed_at = timezone.now()
            refund.save()

            payment.refund_amount += refund.amount
            if payment.refund_amount >= payment.amount:
                payment.status = 'refunded'
            else:
                payment.status = 'partially_refunded'
            payment.refunded_at = timezone.now()
            payment.save()

            if payment.payee:
                payment.payee.wallet_balance -= refund.amount
                payment.payee.save(update_fields=['wallet_balance'])

            Transaction.objects.create(
                user=payment.payer,
                transaction_type='refund',
                amount=refund.amount,
                currency=refund.currency,
                balance_before=payment.payer.wallet_balance,
                balance_after=payment.payer.wallet_balance,
                refund=refund,
                description=f"Refund for {payment.description}",
            )

            if payment.payee:
                Transaction.objects.create(
                    user=payment.payee,
                    transaction_type='refund',
                    amount=-refund.amount,
                    currency=refund.currency,
                    balance_before=payment.payee.wallet_balance + refund.amount,
                    balance_after=payment.payee.wallet_balance,
                    refund=refund,
                    description=f"Refund issued for {payment.description}",
                )

            return {
                'success': True,
                'refund_id': str(refund.id),
                'amount': str(refund.amount),
            }
        except Exception as e:
            refund.status = 'failed'
            refund.failure_reason = str(e)
            refund.save()
            logger.error(f"Error processing refund {refund.id}: {e}")
            raise

    @staticmethod
    @transaction.atomic
    def process_payout(payout):
        """Debit user wallet for a manual payout request (bank / eSewa / Khalti)."""
        from .models import Transaction

        try:
            user = payout.user

            if user.wallet_balance < payout.amount:
                raise ValueError("Insufficient balance")

            payout.processing_fee = payout.amount * Decimal('0.01')
            payout.net_amount = payout.amount - payout.processing_fee
            payout.status = 'paid'
            payout.completed_at = timezone.now()
            payout.save()

            user.wallet_balance -= payout.amount
            user.save(update_fields=['wallet_balance'])

            Transaction.objects.create(
                user=user,
                transaction_type='payout',
                amount=-payout.amount,
                currency=payout.currency,
                balance_before=user.wallet_balance + payout.amount,
                balance_after=user.wallet_balance,
                payout=payout,
                description=f"Payout to {payout.payout_method}",
            )

            return {
                'success': True,
                'payout_id': str(payout.id),
                'amount': str(payout.amount),
                'net_amount': str(payout.net_amount),
            }
        except Exception as e:
            payout.status = 'failed'
            payout.failure_reason = str(e)
            payout.save()
            logger.error(f"Error processing payout {payout.id}: {e}")
            raise

    @staticmethod
    @transaction.atomic
    def release_escrow(payment, release_immediately=False, scheduled_date=None):
        """Release payment from escrow."""
        if not payment.is_escrowed:
            raise ValueError("Payment is not in escrow")

        if release_immediately:
            payment.is_escrowed = False
            payment.escrow_released_at = timezone.now()
            payment.save()
            return {
                'success': True,
                'message': 'Escrow released immediately',
                'released_at': payment.escrow_released_at,
            }
        if scheduled_date:
            payment.escrow_release_scheduled_at = scheduled_date
            payment.save()
            return {
                'success': True,
                'message': 'Escrow release scheduled',
                'scheduled_for': scheduled_date,
            }
        raise ValueError("Must specify release_immediately or scheduled_date")

    @staticmethod
    @transaction.atomic
    def process_direct_payment(payer, payee, amount, description, payment_method='wallet'):
        """Process a direct wallet payment (non-escrow)."""
        fees = EscrowService.calculate_fees(amount, payment_method=payment_method)

        payment = Payment.objects.create(
            payer=payer,
            payee=payee,
            amount=amount,
            platform_fee=fees['platform_fee'],
            payment_processing_fee=fees['payment_processing_fee'],
            net_amount=fees['net_amount'],
            status='succeeded',
            payment_type='task_payment',
            payment_method=payment_method,
            description=description,
            metadata={'total_amount': str(fees['total_amount'])},
            completed_at=timezone.now(),
        )

        wallet, _ = Wallet.objects.get_or_create(user=payee)
        WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type='credit',
            amount=payment.net_amount,
            balance_after=wallet.balance + payment.net_amount,
            description=description,
            reference_type='payment',
            reference_id=str(payment.id),
            status='completed',
        )
        wallet.balance += payment.net_amount
        wallet.save(update_fields=['balance'])

        logger.info("Processed direct payment %s, amount: %s", payment.id, fees['total_amount'])
        return payment


class EscrowService:
    """
    Escrow payment service for marketplace transactions.
    """

    @staticmethod
    def get_escrow_hold_amount(bid) -> Decimal:
        return EscrowService.get_escrow_hold_amount_for_amount(
            bid.amount,
            category_id=getattr(bid.task, 'category_id', None),
            task=bid.task,
        )

    @staticmethod
    def get_escrow_hold_amount_for_amount(
        amount,
        *,
        category_id=None,
        task=None,
    ) -> Decimal:
        from .fee_service import PlatformFeeService

        breakdown = PlatformFeeService.calculate_task_payment_fees(
            amount,
            payment_method='wallet',
            category_id=category_id,
            task=task,
        )
        return breakdown['poster_total_held']

    @staticmethod
    def validate_owner_wallet_for_acceptance(bid) -> None:
        from apps.wallets.services import WalletService

        task = bid.task
        hold_amount = EscrowService.get_escrow_hold_amount(bid)
        wallet, _ = Wallet.objects.get_or_create(user=task.owner)

        if wallet.is_frozen:
            raise ValidationError(
                "Your wallet is frozen. Please contact support before accepting offers."
            )

        if wallet.available_balance < hold_amount:
            currency = bid.currency or wallet.currency or 'NPR'
            raise ValidationError(
                f"Insufficient wallet balance. You need {hold_amount} {currency} available "
                f"to accept this offer (your available balance is {wallet.available_balance} {currency}). "
                "Add funds to your wallet and try again."
            )

    @staticmethod
    def calculate_fees(amount: Decimal, payment_method: str = 'wallet') -> dict:
        from .fee_service import PlatformFeeService

        breakdown = PlatformFeeService.calculate_task_payment_fees(
            amount,
            payment_method=payment_method,
        )
        return {
            'amount': breakdown['gross_amount'],
            'platform_fee': breakdown['platform_fee'],
            'payment_processing_fee': breakdown['processing_fee'],
            'total_fees': breakdown['total_fees'],
            'net_amount': breakdown['net_amount'],
            'total_amount': breakdown['poster_total_held'],
            'fee_breakdown': breakdown,
        }

    @staticmethod
    @transaction.atomic
    def create_escrow_on_bid_acceptance(bid) -> Payment:
        from apps.tasks.models import Task
        from apps.wallets.services import WalletService

        task = bid.task
        task_amount = Decimal(str(bid.amount))
        hold_amount = EscrowService.get_escrow_hold_amount(bid)
        fees = EscrowService.calculate_fees(task_amount, payment_method='wallet')

        EscrowService.validate_owner_wallet_for_acceptance(bid)
        wallet, _ = Wallet.objects.get_or_create(user=task.owner)

        try:
            hold_tx = WalletService.hold_funds(
                wallet,
                hold_amount,
                f"Escrow hold for task: {task.title}",
                metadata={
                    'task_id': str(task.id),
                    'bid_id': str(bid.id),
                    'type': 'escrow',
                },
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        payment = Payment.objects.create(
            payer=task.owner,
            payee=bid.tasker,
            amount=task_amount,
            currency=bid.currency,
            platform_fee=fees['platform_fee'],
            payment_processing_fee=fees['payment_processing_fee'],
            net_amount=fees['net_amount'],
            status='held',
            is_escrowed=True,
            payment_type='task_payment',
            payment_method='wallet',
            content_type=ContentType.objects.get_for_model(Task),
            object_id=task.id,
            description=f"Escrow payment for task: {task.title}",
            metadata={
                'bid_id': str(bid.id),
                'task_id': str(task.id),
                'escrow_source': 'wallet',
                'wallet_hold_transaction_id': str(hold_tx.id),
                'hold_amount': str(hold_amount),
                'task_amount': str(task_amount),
                'fee_breakdown': {
                    k: str(v)
                    for k, v in (fees.get('fee_breakdown') or fees).items()
                },
            },
        )

        from .escrow_lifecycle import EscrowLifecycleService

        EscrowLifecycleService.sync_wallet_escrow_record(bid, payment)

        logger.info(
            "Created wallet escrow payment %s for task %s, held %s %s",
            payment.id,
            task.id,
            hold_amount,
            bid.currency,
        )
        return payment

    @staticmethod
    @transaction.atomic
    def release_escrow_on_completion(task) -> Payment:
        from apps.tasks.models import Task
        from apps.wallets.services import WalletService

        try:
            payment = Payment.objects.get(
                content_type=ContentType.objects.get_for_model(Task),
                object_id=task.id,
                status='held',
            )
        except Payment.DoesNotExist:
            raise ValidationError("No held payment found for this task")

        from .fee_service import PlatformFeeService

        fee_breakdown = PlatformFeeService.apply_fees_to_payment(payment, persist=True)

        is_wallet_escrow = (
            payment.payment_method == 'wallet'
            or (payment.metadata or {}).get('escrow_source') == 'wallet'
        )

        if not is_wallet_escrow:
            raise ValidationError(
                "Only wallet escrow is supported. Legacy card payments cannot be released here."
            )

        payer_wallet, _ = Wallet.objects.get_or_create(user=payment.payer)
        payee_wallet, _ = Wallet.objects.get_or_create(user=payment.payee)
        try:
            fee_note = ''
            if fee_breakdown.get('platform_fee', 0) > 0:
                fee_note = f" (platform fee: {fee_breakdown['platform_fee']} {payment.currency})"
            settle_gross = fee_breakdown.get('poster_total_held') or fee_breakdown.get(
                'total_customer_pays'
            ) or payment.amount
            WalletService.settle_held_to_payee(
                payer_wallet,
                payee_wallet,
                settle_gross,
                payment.net_amount,
                f"Payment for task: {task.title}{fee_note}",
                metadata={
                    'payment_id': str(payment.id),
                    'task_id': str(task.id),
                    'fee_breakdown': {k: str(v) for k, v in fee_breakdown.items()},
                },
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        payment.status = 'released'
        payment.escrow_released_at = timezone.now()
        payment.completed_at = timezone.now()
        payment.save(
            update_fields=['status', 'escrow_released_at', 'completed_at'],
        )

        logger.info(
            "Released escrow payment %s, credited %s to payee %s",
            payment.id,
            payment.net_amount,
            payment.payee_id,
        )
        return payment

    @staticmethod
    @transaction.atomic
    def refund_escrow_on_cancellation(task, reason: str) -> dict:
        from .escrow_lifecycle import EscrowLifecycleService

        result = EscrowLifecycleService.refund_escrow(task, reason=reason)
        if result is None:
            return None
        return {
            'payment': result['payment'],
            'refund_amount': result['refund_amount'],
            'cancellation_fee': result.get('cancellation_fee'),
            'stage': result.get('stage'),
        }

    @staticmethod
    def get_escrow_balance(user) -> dict:
        from django.db.models import Sum

        held_as_payer = Payment.objects.filter(
            payer=user,
            status='held',
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        held_as_payee = Payment.objects.filter(
            payee=user,
            status='held',
        ).aggregate(total=Sum('net_amount'))['total'] or Decimal('0.00')

        return {
            'held_as_payer': held_as_payer,
            'held_as_payee': held_as_payee,
            'total_held': held_as_payer + held_as_payee,
        }


class WalletService:
    """Legacy wallet helpers used by some payment flows."""

    @staticmethod
    @transaction.atomic
    def credit_wallet(user, amount: Decimal, transaction_type: str, reference_id: str, description: str = None):
        wallet, _ = Wallet.objects.get_or_create(user=user)

        tx = WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type='credit',
            amount=amount,
            balance_after=wallet.balance + amount,
            description=description or f"Credit: {transaction_type}",
            reference_type=transaction_type,
            reference_id=reference_id,
            status='completed',
        )

        wallet.balance += amount
        wallet.save(update_fields=['balance'])
        logger.info("Credited %s to wallet %s", amount, wallet.id)
        return tx

    @staticmethod
    @transaction.atomic
    def debit_wallet(user, amount: Decimal, transaction_type: str, reference_id: str, description: str = None):
        wallet = Wallet.objects.get(user=user)

        if wallet.balance < amount:
            raise ValidationError("Insufficient wallet balance")

        tx = WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type='debit',
            amount=amount,
            balance_after=wallet.balance - amount,
            description=description or f"Debit: {transaction_type}",
            reference_type=transaction_type,
            reference_id=reference_id,
            status='completed',
        )

        wallet.balance -= amount
        wallet.save(update_fields=['balance'])
        logger.info("Debited %s from wallet %s", amount, wallet.id)
        return tx

    @staticmethod
    def get_wallet_balance(user) -> Decimal:
        try:
            wallet = Wallet.objects.get(user=user)
            return wallet.balance
        except Wallet.DoesNotExist:
            return Decimal('0.00')
