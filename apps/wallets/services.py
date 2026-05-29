from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import logging

from .utils import is_wallet_recharge_from_meta

logger = logging.getLogger(__name__)


def _counts_as_task_earning(metadata, description):
    if is_wallet_recharge_from_meta(metadata, description):
        return False
    meta = metadata or {}
    if meta.get('settlement_type') == 'escrow_receive':
        return True
    if meta.get('payment_id'):
        return True
    desc = (description or '').lower()
    return 'payment received' in desc


class WalletService:
    """
    Service for wallet operations and business logic
    """

    PENDING_WITHDRAWAL_STATUSES = ('pending',)

    @staticmethod
    def pending_withdrawal_total(wallet):
        """Sum of withdrawal amounts awaiting admin review (not yet debited)."""
        from django.db.models import Sum
        from .models import WithdrawalRequest

        total = (
            WithdrawalRequest.objects.filter(
                wallet=wallet,
                status__in=WalletService.PENDING_WITHDRAWAL_STATUSES,
            ).aggregate(total=Sum('amount'))['total']
        )
        return total or Decimal('0')

    @staticmethod
    def withdrawable_balance(wallet):
        """
        Amount the user can request in a new withdrawal without exceeding
        available balance, accounting for other pending requests.
        """
        if wallet.is_frozen:
            return Decimal('0')
        remaining = wallet.available_balance - WalletService.pending_withdrawal_total(wallet)
        return max(remaining, Decimal('0'))

    @staticmethod
    def can_withdraw_amount(wallet, amount):
        return WalletService.withdrawable_balance(wallet) >= amount
    
    @staticmethod
    @transaction.atomic
    def credit_wallet(wallet, amount, description, transaction_type='credit', metadata=None):
        """
        Credit amount to wallet
        """
        from .models import WalletTransaction
        
        if amount <= 0:
            raise ValueError("Amount must be greater than 0")
        
        # Update wallet balance (recharges do not count toward task earnings)
        balance_before = wallet.available_balance
        wallet.available_balance += amount
        if _counts_as_task_earning(metadata, description):
            wallet.total_earned += amount
        wallet.save()
        
        # Create transaction record
        transaction_obj = WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type=transaction_type,
            amount=amount,
            currency=wallet.currency,
            status='completed',
            balance_before=balance_before,
            balance_after=wallet.available_balance,
            description=description,
            metadata=metadata or {},
            completed_at=timezone.now()
        )
        
        return transaction_obj
    
    @staticmethod
    @transaction.atomic
    def debit_wallet(wallet, amount, description, transaction_type='debit', metadata=None):
        """
        Debit amount from wallet
        """
        from .models import WalletTransaction
        
        if amount <= 0:
            raise ValueError("Amount must be greater than 0")
        
        if wallet.available_balance < amount:
            raise ValueError("Insufficient balance")
        
        # Update wallet balance
        balance_before = wallet.available_balance
        wallet.available_balance -= amount
        wallet.save()
        
        # Create transaction record
        transaction_obj = WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type=transaction_type,
            amount=amount,
            currency=wallet.currency,
            status='completed',
            balance_before=balance_before,
            balance_after=wallet.available_balance,
            description=description,
            metadata=metadata or {},
            completed_at=timezone.now()
        )
        
        return transaction_obj
    
    @staticmethod
    @transaction.atomic
    def hold_funds(wallet, amount, description, metadata=None):
        """
        Hold funds in escrow
        """
        from .models import WalletTransaction
        
        if amount <= 0:
            raise ValueError("Amount must be greater than 0")
        
        if wallet.available_balance < amount:
            raise ValueError("Insufficient balance")
        
        # Move from available to held
        balance_before = wallet.available_balance
        wallet.available_balance -= amount
        wallet.held_balance += amount
        wallet.save()
        
        # Create transaction record
        transaction_obj = WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type='hold',
            amount=amount,
            currency=wallet.currency,
            status='completed',
            balance_before=balance_before,
            balance_after=wallet.available_balance,
            description=description,
            metadata=metadata or {},
            completed_at=timezone.now()
        )
        
        return transaction_obj
    
    @staticmethod
    @transaction.atomic
    def release_funds(wallet, amount, description, metadata=None):
        """
        Release held funds
        """
        from .models import WalletTransaction
        
        if amount <= 0:
            raise ValueError("Amount must be greater than 0")
        
        if wallet.held_balance < amount:
            raise ValueError("Insufficient held balance")
        
        # Move from held to available
        balance_before = wallet.available_balance
        wallet.held_balance -= amount
        wallet.available_balance += amount
        wallet.save()
        
        # Create transaction record
        transaction_obj = WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type='release',
            amount=amount,
            currency=wallet.currency,
            status='completed',
            balance_before=balance_before,
            balance_after=wallet.available_balance,
            description=description,
            metadata=metadata or {},
            completed_at=timezone.now()
        )
        
        return transaction_obj
    
    @staticmethod
    @transaction.atomic
    def settle_held_to_payee(payer_wallet, payee_wallet, gross_amount, net_amount, description, metadata=None):
        """
        Settle escrow held on the payer wallet by paying the tasker the net amount.
        Platform fee (gross - net) is not returned to the payer.
        """
        from .models import WalletTransaction

        gross_amount = Decimal(str(gross_amount))
        net_amount = Decimal(str(net_amount))

        if gross_amount <= 0 or net_amount <= 0:
            raise ValueError("Amounts must be greater than 0")
        if net_amount > gross_amount:
            raise ValueError("Net amount cannot exceed gross amount")
        if payer_wallet.held_balance < gross_amount:
            raise ValueError("Insufficient held balance")
        if payer_wallet.currency != payee_wallet.currency:
            raise ValueError("Currency mismatch")

        balance_before = payer_wallet.held_balance
        payer_wallet.held_balance -= gross_amount
        payer_wallet.save()

        WalletTransaction.objects.create(
            wallet=payer_wallet,
            transaction_type='debit',
            amount=gross_amount,
            currency=payer_wallet.currency,
            status='completed',
            balance_before=balance_before,
            balance_after=payer_wallet.held_balance,
            description=description,
            metadata={**(metadata or {}), 'settlement_type': 'escrow_payout'},
            completed_at=timezone.now(),
        )

        return WalletService.credit_wallet(
            payee_wallet,
            net_amount,
            description,
            transaction_type='credit',
            metadata={**(metadata or {}), 'settlement_type': 'escrow_receive'},
        )
    
    @staticmethod
    def withdrawal_debit_applied(withdrawal_request) -> bool:
        """True if wallet was already debited for this withdrawal."""
        from .models import WalletTransaction

        withdrawal_id = str(withdrawal_request.id)
        return WalletTransaction.objects.filter(
            wallet_id=withdrawal_request.wallet_id,
            transaction_type='debit',
            status__in=['pending', 'completed'],
            metadata__withdrawal_id=withdrawal_id,
        ).exists()

    @staticmethod
    def _complete_withdrawal_transactions(withdrawal_request, wallet):
        from .models import WalletTransaction

        withdrawal_id = str(withdrawal_request.id)
        now = timezone.now()
        WalletTransaction.objects.filter(
            wallet=wallet,
            transaction_type='debit',
            status='pending',
            metadata__withdrawal_id=withdrawal_id,
        ).update(
            status='completed',
            completed_at=now,
            description=f"Withdrawal via {withdrawal_request.withdrawal_method}",
        )

    @staticmethod
    @transaction.atomic
    def register_pending_withdrawal(wallet, withdrawal_request):
        """
        Record a pending withdrawal without changing available_balance.
        Balance is debited when admin approves (process_withdrawal).
        """
        from .models import Wallet

        wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
        # NOTE:
        # The withdrawal request is already persisted with status='pending' when this
        # is called. If we re-check "withdrawable balance" here, the pending total
        # includes this same request and can incorrectly fail (self-counting).
        # Validation must happen before creating the request (see perform_create +
        # serializer validate_amount).

        meta = dict(withdrawal_request.metadata or {})
        meta['funds_reserved'] = False
        meta['pending_registered_at'] = timezone.now().isoformat()
        withdrawal_request.metadata = meta
        withdrawal_request.save(update_fields=['metadata', 'updated_at'])

        return wallet

    @staticmethod
    @transaction.atomic
    def reserve_for_withdrawal(wallet, withdrawal_request):
        """Deprecated alias — pending withdrawals no longer reserve balance."""
        return WalletService.register_pending_withdrawal(wallet, withdrawal_request)

    @staticmethod
    @transaction.atomic
    def release_withdrawal_reservation(withdrawal_request) -> bool:
        """Return reserved funds when a pending withdrawal is rejected or cancelled."""
        from .models import Wallet, WalletTransaction

        meta = dict(withdrawal_request.metadata or {})
        if not meta.get('funds_reserved'):
            return False

        wallet = Wallet.objects.select_for_update().get(pk=withdrawal_request.wallet_id)
        wallet.available_balance += withdrawal_request.amount
        wallet.save(update_fields=['available_balance', 'updated_at'])

        withdrawal_id = str(withdrawal_request.id)
        WalletTransaction.objects.filter(
            wallet=wallet,
            transaction_type='debit',
            status='pending',
            metadata__withdrawal_id=withdrawal_id,
        ).update(status='cancelled')

        meta['funds_reserved'] = False
        withdrawal_request.metadata = meta
        withdrawal_request.save(update_fields=['metadata', 'updated_at'])
        return True

    @staticmethod
    @transaction.atomic
    def apply_missing_withdrawal_debit(withdrawal_request, approved_by):
        """
        Fix withdrawals marked approved in admin without running the approve API
        (balance was never debited).
        """
        from .models import Wallet, WalletTransaction

        if WalletService.withdrawal_debit_applied(withdrawal_request):
            return {
                'success': True,
                'message': 'Wallet already debited for this withdrawal',
                'withdrawal_id': str(withdrawal_request.id),
            }

        wallet = Wallet.objects.select_for_update().get(pk=withdrawal_request.wallet_id)
        if wallet.is_frozen:
            raise ValueError("Wallet is frozen")
        if wallet.available_balance < withdrawal_request.amount:
            raise ValueError(
                f"Insufficient balance (available {wallet.available_balance} {wallet.currency}, "
                f"required {withdrawal_request.amount} {wallet.currency})."
            )

        balance_before = wallet.available_balance
        wallet.available_balance -= withdrawal_request.amount
        wallet.total_withdrawn += withdrawal_request.amount
        wallet.save(update_fields=['available_balance', 'total_withdrawn', 'updated_at'])

        WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type='debit',
            amount=withdrawal_request.amount,
            currency=wallet.currency,
            status='completed',
            balance_before=balance_before,
            balance_after=wallet.available_balance,
            description=f"Withdrawal via {withdrawal_request.withdrawal_method}",
            metadata={
                'withdrawal_id': str(withdrawal_request.id),
                'method': withdrawal_request.withdrawal_method,
                'backfill': True,
            },
            completed_at=timezone.now(),
        )

        if not withdrawal_request.approved_by_id:
            withdrawal_request.approved_by = approved_by
            withdrawal_request.approved_at = timezone.now()

        if withdrawal_request.status == 'approved':
            withdrawal_request.status = 'processing'

        withdrawal_request.save(
            update_fields=['status', 'approved_by', 'approved_at', 'updated_at']
        )

        return {
            'success': True,
            'message': 'Missing wallet debit applied',
            'withdrawal_id': str(withdrawal_request.id),
            'amount': str(withdrawal_request.amount),
            'net_amount': str(withdrawal_request.net_amount),
        }

    @staticmethod
    @transaction.atomic
    def process_withdrawal(withdrawal_request, approved_by):
        """
        Approve a pending withdrawal: finalize reserved funds or debit legacy requests.
        """
        from .models import Wallet, WalletTransaction

        wallet = Wallet.objects.select_for_update().get(pk=withdrawal_request.wallet_id)

        if wallet.is_frozen:
            raise ValueError("Wallet is frozen")

        meta = dict(withdrawal_request.metadata or {})
        already_debited = WalletService.withdrawal_debit_applied(withdrawal_request)

        if already_debited:
            # Legacy requests that reserved balance at submit time.
            if meta.get('funds_reserved'):
                wallet.total_withdrawn += withdrawal_request.amount
                wallet.save(update_fields=['total_withdrawn', 'updated_at'])
            WalletService._complete_withdrawal_transactions(withdrawal_request, wallet)
        else:
            if wallet.available_balance < withdrawal_request.amount:
                raise ValueError(
                    f"Insufficient balance (available {wallet.available_balance} {wallet.currency}, "
                    f"required {withdrawal_request.amount} {wallet.currency})."
                )

            balance_before = wallet.available_balance
            wallet.available_balance -= withdrawal_request.amount
            wallet.total_withdrawn += withdrawal_request.amount
            wallet.save(
                update_fields=['available_balance', 'total_withdrawn', 'updated_at']
            )

            WalletTransaction.objects.create(
                wallet=wallet,
                transaction_type='debit',
                amount=withdrawal_request.amount,
                currency=wallet.currency,
                status='completed',
                balance_before=balance_before,
                balance_after=wallet.available_balance,
                description=f"Withdrawal via {withdrawal_request.withdrawal_method}",
                metadata={
                    'withdrawal_id': str(withdrawal_request.id),
                    'method': withdrawal_request.withdrawal_method,
                },
                completed_at=timezone.now(),
            )

        withdrawal_request.status = 'approved'
        withdrawal_request.approved_by = approved_by
        withdrawal_request.approved_at = timezone.now()
        withdrawal_request.save(
            update_fields=['status', 'approved_by', 'approved_at', 'updated_at']
        )

        return {
            'success': True,
            # Keep as "approved" until an external payout is actually initiated.
            'message': 'Withdrawal approved',
            'withdrawal_id': str(withdrawal_request.id),
            'amount': str(withdrawal_request.amount),
            'net_amount': str(withdrawal_request.net_amount),
        }
    
    @staticmethod
    def check_withdrawal_limit(wallet, amount, limit_type='daily_withdrawal'):
        """
        Check if withdrawal amount exceeds limits
        """
        from .models import WalletLimit, WithdrawalRequest
        from datetime import timedelta
        
        # Get limit
        limit = WalletLimit.objects.filter(
            wallet=wallet,
            limit_type=limit_type,
            is_active=True
        ).first()
        
        if not limit:
            return True  # No limit set
        
        # Calculate time range
        now = timezone.now()
        if limit_type == 'daily_withdrawal':
            start_time = now - timedelta(days=1)
        elif limit_type == 'weekly_withdrawal':
            start_time = now - timedelta(weeks=1)
        elif limit_type == 'monthly_withdrawal':
            start_time = now - timedelta(days=30)
        else:
            return True
        
        # Get total withdrawn in period
        total_withdrawn = WithdrawalRequest.objects.filter(
            wallet=wallet,
            status__in=['approved', 'processing', 'completed'],
            created_at__gte=start_time
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        
        # Check if adding this amount would exceed limit
        return (total_withdrawn + amount) <= limit.amount
    
    @staticmethod
    @transaction.atomic
    def transfer_between_wallets(from_wallet, to_wallet, amount, description):
        """
        Transfer funds between two wallets
        """
        if amount <= 0:
            raise ValueError("Amount must be greater than 0")
        
        if from_wallet.currency != to_wallet.currency:
            raise ValueError("Currency mismatch")
        
        # Debit from source wallet
        WalletService.debit_wallet(
            from_wallet,
            amount,
            f"Transfer to {to_wallet.user.email}: {description}",
            transaction_type='debit',
            metadata={'transfer_to': str(to_wallet.id)}
        )
        
        # Credit to destination wallet
        WalletService.credit_wallet(
            to_wallet,
            amount,
            f"Transfer from {from_wallet.user.email}: {description}",
            transaction_type='credit',
            metadata={'transfer_from': str(from_wallet.id)}
        )
        
        return {
            'success': True,
            'message': 'Transfer completed',
            'amount': str(amount),
            'from': from_wallet.user.email,
            'to': to_wallet.user.email
        }
