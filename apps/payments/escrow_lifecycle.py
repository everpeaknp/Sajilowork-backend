"""
Production escrow lifecycle — state machine, gateway funding, release, refund, audit.
"""
from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.tasks.models import Task
from apps.wallets.models import Wallet
from apps.wallets.services import WalletService

from .escrow_constants import (
    CANCELLED,
    COMPLETED,
    DISPUTED,
    ESCROW_TRANSITIONS,
    FUNDED,
    IN_PROGRESS,
    PENDING_PAYMENT,
    REFUNDED,
    RELEASED,
    SUBMITTED,
    PAYMENT_TX_FAILED,
    PAYMENT_TX_PENDING,
    PAYMENT_TX_SUCCESS,
)
from .models import Escrow, EscrowAuditLog, Payment, PaymentTransaction

logger = logging.getLogger(__name__)


class EscrowLifecycleError(ValidationError):
    """Escrow operation not allowed in current state."""


class EscrowLifecycleService:
    """Authoritative escrow orchestration (platform-controlled ledger)."""

    @staticmethod
    def auto_release_hours() -> int:
        return int(getattr(settings, 'ESCROW_AUTO_RELEASE_HOURS', 48))

    @staticmethod
    def get_escrow_for_task(task_id) -> Escrow | None:
        return (
            Escrow.objects.select_related('payment', 'task', 'bid', 'payer', 'payee')
            .filter(task_id=task_id)
            .order_by('-created_at')
            .first()
        )

    @staticmethod
    def _transition(escrow: Escrow, new_status: str, *, actor=None, note: str = '', metadata: dict | None = None):
        allowed = ESCROW_TRANSITIONS.get(escrow.status, set())
        if new_status not in allowed:
            raise EscrowLifecycleError(
                f'Cannot transition escrow from {escrow.status} to {new_status}.'
            )
        old = escrow.status
        escrow.status = new_status
        now = timezone.now()
        if new_status == FUNDED and not escrow.locked_at:
            escrow.locked_at = now
        if new_status == RELEASED and not escrow.released_at:
            escrow.released_at = now
        if new_status == REFUNDED and not escrow.refunded_at:
            escrow.refunded_at = now
        escrow.save()
        EscrowAuditLog.objects.create(
            escrow=escrow,
            from_status=old,
            to_status=new_status,
            actor=actor,
            note=note,
            metadata=metadata or {},
        )
        logger.info('Escrow %s: %s -> %s', escrow.id, old, new_status)

    @staticmethod
    def _cancellation_stage(task: Task) -> str:
        from apps.fees.models import FeeRule

        if task.status in ('in_progress', 'pending_approval'):
            return FeeRule.CancellationStage.IN_PROGRESS
        if task.status == 'assigned':
            return FeeRule.CancellationStage.AFTER_ACCEPT
        return FeeRule.CancellationStage.BEFORE_ACCEPT

    @staticmethod
    @transaction.atomic
    def create_pending_gateway_escrow(
        *,
        bid,
        payer,
        provider: str,
        idempotency_key: str,
        success_url: str,
        failure_url: str,
    ) -> dict:
        """STEP 1 (gateway): create pending escrow before redirect to eSewa/Khalti."""
        from .fee_service import PlatformFeeService
        from .gateways.esewa import ESewaGateway
        from .gateways.khalti import KhaltiGateway

        task = bid.task
        if task.owner_id != payer.id:
            raise PermissionDenied('Only the task owner can fund escrow.')

        if PaymentTransaction.objects.filter(idempotency_key=idempotency_key).exists():
            existing = PaymentTransaction.objects.get(idempotency_key=idempotency_key)
            return {
                'payment_transaction_id': str(existing.id),
                'status': existing.status,
                'duplicate': True,
            }

        task_amount = Decimal(str(bid.amount))
        fees = PlatformFeeService.calculate_task_payment_fees(
            task_amount,
            payment_method=provider,
            category_id=getattr(task, 'category_id', None),
            task=task,
        )
        hold_amount = fees['poster_total_held']

        payment = Payment.objects.create(
            payer=payer,
            payee=bid.tasker,
            amount=task_amount,
            currency=bid.currency or 'NPR',
            platform_fee=fees['platform_fee'],
            payment_processing_fee=fees['processing_fee'],
            net_amount=fees['net_amount'],
            status='pending',
            payment_type='task_payment',
            payment_method=provider,
            is_escrowed=True,
            content_type=ContentType.objects.get_for_model(Task),
            object_id=task.id,
            description=f'Escrow funding for task: {task.title}',
            metadata={
                'bid_id': str(bid.id),
                'task_id': str(task.id),
                'escrow_source': provider,
                'hold_amount': str(hold_amount),
                'fee_breakdown': {k: str(v) for k, v in fees.items()},
            },
        )

        escrow = Escrow.objects.create(
            payment=payment,
            task=task,
            bid=bid,
            payer=payer,
            payee=bid.tasker,
            amount=task_amount,
            platform_fee=fees['platform_fee'],
            processing_fee=fees['processing_fee'],
            net_amount=fees['net_amount'],
            currency=payment.currency,
            status=PENDING_PAYMENT,
            funding_method=provider,
            idempotency_key=idempotency_key,
        )

        gateway_tx_id = f'escrow-{escrow.id}-{uuid.uuid4().hex[:8]}'
        pt = PaymentTransaction.objects.create(
            escrow=escrow,
            payment=payment,
            provider=provider,
            transaction_id=gateway_tx_id,
            idempotency_key=idempotency_key,
            amount=hold_amount,
            currency=payment.currency,
            status=PAYMENT_TX_PENDING,
            payer=payer,
            metadata={'task_id': str(task.id), 'bid_id': str(bid.id)},
        )

        if provider == 'esewa':
            gateway = ESewaGateway()
            result = gateway.initiate_payment(
                amount=hold_amount,
                transaction_id=gateway_tx_id,
                product_name=f'Task escrow: {task.title[:40]}',
                success_url=success_url,
                failure_url=failure_url,
            )
        elif provider == 'khalti':
            gateway = KhaltiGateway()
            result = gateway.initiate_payment(
                amount=hold_amount,
                transaction_id=gateway_tx_id,
                product_name=f'Task escrow: {task.title[:40]}',
                customer_info={
                    'name': payer.get_full_name() or payer.email,
                    'email': payer.email,
                },
                success_url=success_url,
                failure_url=failure_url,
            )
        else:
            raise ValidationError(f'Unsupported provider: {provider}')

        if not result.get('success'):
            pt.status = PAYMENT_TX_FAILED
            pt.failure_reason = result.get('error', 'initiation failed')
            pt.save(update_fields=['status', 'failure_reason'])
            raise ValidationError(pt.failure_reason)

        pt.metadata['gateway'] = {k: v for k, v in result.items() if k != 'success'}
        pt.save(update_fields=['metadata'])

        EscrowAuditLog.objects.create(
            escrow=escrow,
            from_status='',
            to_status=PENDING_PAYMENT,
            actor=payer,
            note=f'Gateway payment initiated via {provider}',
            metadata={'payment_transaction_id': str(pt.id)},
        )

        return {
            'escrow_id': str(escrow.id),
            'payment_id': str(payment.id),
            'payment_transaction_id': str(pt.id),
            'payment_url': result.get('payment_url'),
            'pidx': result.get('pidx'),
            'transaction_id': gateway_tx_id,
            'amount': str(hold_amount),
            'currency': payment.currency,
            'status': PENDING_PAYMENT,
        }

    @staticmethod
    @transaction.atomic
    def verify_gateway_and_fund(
        *,
        payer,
        transaction_id: str,
        provider: str,
        pidx: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        """STEP 1 complete: verify gateway payment and lock funds in escrow (held_balance)."""
        from .gateways.esewa import ESewaGateway
        from .gateways.khalti import KhaltiGateway

        pt = PaymentTransaction.objects.select_related(
            'escrow', 'payment', 'escrow__task', 'escrow__bid',
        ).filter(transaction_id=transaction_id, payer=payer).first()

        if not pt:
            raise ValidationError('Payment transaction not found.')

        if idempotency_key and pt.idempotency_key != idempotency_key:
            raise ValidationError('Idempotency key mismatch.')

        if pt.status == PAYMENT_TX_SUCCESS:
            return {
                'verified': True,
                'duplicate': True,
                'escrow_id': str(pt.escrow_id),
                'status': pt.escrow.status,
            }

        escrow = pt.escrow
        payment = pt.payment
        task = escrow.task
        bid = escrow.bid

        if provider == 'esewa':
            result = ESewaGateway().verify_payment(transaction_id=transaction_id)
        elif provider == 'khalti':
            if not pidx:
                raise ValidationError('pidx is required for Khalti verification.')
            result = KhaltiGateway().verify_payment(transaction_id=transaction_id, pidx=pidx)
        else:
            raise ValidationError(f'Unsupported provider: {provider}')

        if not result.get('verified'):
            pt.status = PAYMENT_TX_FAILED
            pt.failure_reason = result.get('error', 'verification failed')
            pt.verified_at = timezone.now()
            pt.save(update_fields=['status', 'failure_reason', 'verified_at'])
            payment.status = 'failed'
            payment.failure_reason = pt.failure_reason
            payment.save(update_fields=['status', 'failure_reason'])
            raise ValidationError(pt.failure_reason)

        verified_amount = Decimal(str(result.get('amount', pt.amount)))
        hold_amount = Decimal(str((payment.metadata or {}).get('hold_amount', pt.amount)))

        if verified_amount < hold_amount:
            raise ValidationError('Verified amount is less than required escrow hold.')

        wallet, _ = Wallet.objects.select_for_update().get_or_create(user=payer)
        if wallet.is_frozen:
            raise ValidationError('Wallet is frozen.')

        WalletService.credit_wallet(
            wallet,
            hold_amount,
            f'Escrow funding ({provider}) for task: {task.title}',
            metadata={
                'type': 'escrow_fund',
                'payment_transaction_id': str(pt.id),
                'escrow_id': str(escrow.id),
                'provider': provider,
            },
        )
        hold_tx = WalletService.hold_funds(
            wallet,
            hold_amount,
            f'Escrow hold for task: {task.title}',
            metadata={
                'task_id': str(task.id),
                'bid_id': str(bid.id),
                'type': 'escrow',
                'escrow_id': str(escrow.id),
            },
        )

        pt.status = PAYMENT_TX_SUCCESS
        pt.verified_at = timezone.now()
        pt.provider_reference = result.get('reference_id', '') or result.get('transaction_uuid', '')
        pt.metadata['verify_result'] = {k: str(v) for k, v in result.items()}
        pt.save()

        payment.status = 'held'
        payment.metadata['wallet_hold_transaction_id'] = str(hold_tx.id)
        payment.metadata['escrow_source'] = provider
        payment.completed_at = timezone.now()
        payment.save(update_fields=['status', 'metadata', 'completed_at'])

        EscrowLifecycleService._transition(
            escrow,
            FUNDED,
            actor=payer,
            note=f'Gateway payment verified ({provider})',
            metadata={'amount': str(hold_amount)},
        )

        return {
            'verified': True,
            'escrow_id': str(escrow.id),
            'payment_id': str(payment.id),
            'status': escrow.status,
            'task_id': str(task.id),
            'bid_id': str(bid.id),
        }

    @staticmethod
    @transaction.atomic
    def sync_wallet_escrow_record(bid, payment: Payment) -> Escrow:
        """Create or update Escrow row when wallet hold succeeds on bid acceptance."""
        task = bid.task
        escrow, created = Escrow.objects.get_or_create(
            task=task,
            defaults={
                'bid': bid,
                'payment': payment,
                'payer': task.owner,
                'payee': bid.tasker,
                'amount': payment.amount,
                'platform_fee': payment.platform_fee,
                'processing_fee': payment.payment_processing_fee,
                'net_amount': payment.net_amount or payment.amount,
                'currency': payment.currency,
                'status': FUNDED,
                'funding_method': 'wallet',
                'locked_at': timezone.now(),
            },
        )
        if not created:
            escrow.payment = payment
            escrow.status = FUNDED
            escrow.locked_at = escrow.locked_at or timezone.now()
            escrow.save()
        EscrowAuditLog.objects.create(
            escrow=escrow,
            from_status='' if created else PENDING_PAYMENT,
            to_status=FUNDED,
            actor=task.owner,
            note='Wallet escrow funded on bid acceptance',
        )
        return escrow

    @staticmethod
    def on_task_started(task: Task, actor=None):
        escrow = EscrowLifecycleService.get_escrow_for_task(task.id)
        if escrow and escrow.status == FUNDED:
            EscrowLifecycleService._transition(
                escrow, IN_PROGRESS, actor=actor, note='Task work started',
            )

    @staticmethod
    def on_completion_submitted(task: Task, actor=None):
        escrow = EscrowLifecycleService.get_escrow_for_task(task.id)
        if escrow and escrow.status == IN_PROGRESS:
            EscrowLifecycleService._transition(
                escrow, SUBMITTED, actor=actor, note='Completion submitted for approval',
            )
            escrow.auto_release_at = timezone.now() + timedelta(
                hours=EscrowLifecycleService.auto_release_hours()
            )
            escrow.save(update_fields=['auto_release_at'])

    @staticmethod
    def on_task_completed(task: Task, actor=None):
        escrow = EscrowLifecycleService.get_escrow_for_task(task.id)
        if escrow and escrow.status in (SUBMITTED, IN_PROGRESS):
            EscrowLifecycleService._transition(
                escrow, COMPLETED, actor=actor, note='Task completion approved',
            )

    @staticmethod
    def on_escrow_released(task: Task, actor=None):
        escrow = EscrowLifecycleService.get_escrow_for_task(task.id)
        if escrow and escrow.status == COMPLETED:
            EscrowLifecycleService._transition(
                escrow, RELEASED, actor=actor, note='Funds released to tasker wallet',
            )
            escrow.auto_release_at = None
            escrow.save(update_fields=['auto_release_at'])

    @staticmethod
    def on_escrow_refunded(task: Task, actor=None, reason: str = ''):
        escrow = EscrowLifecycleService.get_escrow_for_task(task.id)
        if escrow and escrow.status not in (RELEASED, REFUNDED, CANCELLED):
            EscrowLifecycleService._transition(
                escrow, REFUNDED, actor=actor, note=reason or 'Escrow refunded',
            )

    @staticmethod
    def on_escrow_cancelled(task: Task, actor=None, reason: str = ''):
        escrow = EscrowLifecycleService.get_escrow_for_task(task.id)
        if escrow and escrow.status not in (RELEASED, REFUNDED, CANCELLED):
            EscrowLifecycleService._transition(
                escrow, CANCELLED, actor=actor, note=reason or 'Escrow cancelled',
            )

    @staticmethod
    def schedule_auto_release(task: Task):
        escrow = EscrowLifecycleService.get_escrow_for_task(task.id)
        if escrow and escrow.status == COMPLETED:
            escrow.auto_release_at = timezone.now() + timedelta(
                hours=EscrowLifecycleService.auto_release_hours()
            )
            escrow.save(update_fields=['auto_release_at'])

    @staticmethod
    def release_stale_completed_escrows_for_user(user) -> int:
        """
        Release held escrow for tasks already marked completed but never paid out
        (e.g. completed before update_status wired escrow release).
        """
        from django.contrib.contenttypes.models import ContentType

        task_ct = ContentType.objects.get_for_model(Task)
        held_payments = Payment.objects.filter(
            payee=user,
            status='held',
            content_type=task_ct,
            payment_type='task_payment',
        )

        released = 0
        for payment in held_payments:
            try:
                task = Task.objects.get(pk=payment.object_id)
            except Task.DoesNotExist:
                continue
            if task.assigned_tasker_id != user.id:
                continue
            from apps.tasks.completion_service import ready_for_payout

            if not ready_for_payout(task):
                continue
            try:
                EscrowLifecycleService.release_escrow_for_completed_task(
                    task, actor=user
                )
                released += 1
            except (EscrowLifecycleError, ValidationError) as exc:
                logger.warning(
                    'Stale escrow release skipped for task %s: %s',
                    task.id,
                    exc,
                )
        return released

    @staticmethod
    @transaction.atomic
    def release_escrow_for_completed_task(task: Task, *, actor=None) -> Payment | None:
        """
        Sync escrow state and pay the tasker when a task is marked completed
        (e.g. via PATCH update_status). Idempotent if already released.
        """
        from .services import EscrowService

        escrow = EscrowLifecycleService.get_escrow_for_task(task.id)
        if not escrow:
            try:
                return EscrowService.release_escrow_on_completion(task)
            except ValidationError:
                logger.warning(
                    'Task %s completed but no escrow/payment found to release',
                    task.id,
                )
                return None

        if escrow.status == RELEASED:
            return escrow.payment

        if escrow.status == FUNDED:
            EscrowLifecycleService.on_task_started(task, actor=actor)

        escrow.refresh_from_db()
        # Direct task completion skips pending_approval — escrow must go
        # in_progress → submitted → completed (not in_progress → completed).
        if escrow.status == IN_PROGRESS:
            EscrowLifecycleService.on_completion_submitted(task, actor=actor)
            escrow.refresh_from_db()
        if escrow.status == SUBMITTED:
            EscrowLifecycleService.on_task_completed(task, actor=actor)

        return EscrowLifecycleService.release_escrow(task, actor=actor)

    @staticmethod
    @transaction.atomic
    def release_escrow(task: Task, *, actor=None, force: bool = False) -> Payment:
        """STEP 3: release held funds to tasker after completion (idempotent)."""
        from .services import EscrowService

        escrow = EscrowLifecycleService.get_escrow_for_task(task.id)
        if escrow and escrow.status == RELEASED:
            return escrow.payment

        if escrow and escrow.status not in (COMPLETED, SUBMITTED) and not force:
            if escrow.status == SUBMITTED and force is False:
                raise EscrowLifecycleError(
                    'Task completion must be approved before release.'
                )

        payment = EscrowService.release_escrow_on_completion(task)
        EscrowLifecycleService.on_escrow_released(task, actor=actor)
        return payment

    @staticmethod
    @transaction.atomic
    def refund_escrow(
        task: Task,
        *,
        reason: str,
        actor=None,
        cancellation_stage: str | None = None,
    ) -> dict | None:
        """Refund poster with optional cancellation fee / partial tasker payout."""
        from apps.fees.engine import FeeEngine
        from .models import Refund

        escrow = EscrowLifecycleService.get_escrow_for_task(task.id)
        if escrow and escrow.status in (REFUNDED, CANCELLED):
            return None

        try:
            payment = Payment.objects.select_for_update().get(
                content_type=ContentType.objects.get_for_model(Task),
                object_id=task.id,
                status='held',
            )
        except Payment.DoesNotExist:
            logger.warning('No held payment for task %s', task.id)
            EscrowLifecycleService.on_escrow_cancelled(task, actor=actor, reason=reason)
            return None

        stage = cancellation_stage or EscrowLifecycleService._cancellation_stage(task)
        hold_amount = Decimal(str((payment.metadata or {}).get('hold_amount', payment.amount)))
        cancel_line = FeeEngine.calculate_cancellation(hold_amount, stage)
        cancel_fee = cancel_line.amount

        payer_wallet, _ = Wallet.objects.select_for_update().get_or_create(user=payment.payer)
        payee_wallet, _ = Wallet.objects.select_for_update().get_or_create(user=payment.payee)

        refund_to_poster = hold_amount - cancel_fee
        if refund_to_poster < 0:
            refund_to_poster = Decimal('0.00')

        partial_to_tasker = Decimal('0.00')
        from apps.fees.models import FeeRule

        if stage == FeeRule.CancellationStage.IN_PROGRESS and cancel_fee > 0:
            partial_to_tasker = min(cancel_fee, hold_amount)

        if payment.payment_method == 'wallet' or (payment.metadata or {}).get('escrow_source'):
            if partial_to_tasker > 0:
                WalletService.settle_held_to_payee(
                    payer_wallet,
                    payee_wallet,
                    partial_to_tasker,
                    partial_to_tasker,
                    f'Partial payment for cancelled task: {task.title}',
                    metadata={'task_id': str(task.id), 'cancellation_stage': stage},
                )
            if refund_to_poster > 0:
                WalletService.release_funds(
                    payer_wallet,
                    refund_to_poster,
                    f'Escrow refund for cancelled task: {task.title}',
                    metadata={
                        'payment_id': str(payment.id),
                        'cancellation_fee': str(cancel_fee),
                        'stage': stage,
                    },
                )
            elif partial_to_tasker == 0:
                WalletService.release_funds(
                    payer_wallet,
                    hold_amount,
                    f'Escrow release on cancel: {task.title}',
                    metadata={'payment_id': str(payment.id)},
                )

        payment.status = 'refunded'
        payment.refunded_at = timezone.now()
        payment.refund_amount = refund_to_poster
        payment.metadata['cancellation_stage'] = stage
        payment.metadata['cancellation_fee'] = str(cancel_fee)
        payment.save()

        Refund.objects.create(
            payment=payment,
            amount=refund_to_poster,
            currency=payment.currency,
            reason='task_cancelled',
            status='succeeded',
            description=reason or f'Escrow refund ({stage})',
            completed_at=timezone.now(),
        )

        EscrowLifecycleService.on_escrow_refunded(task, actor=actor, reason=reason)

        return {
            'payment': payment,
            'refund_amount': float(refund_to_poster),
            'cancellation_fee': float(cancel_fee),
            'partial_to_tasker': float(partial_to_tasker),
            'stage': stage,
        }

    @staticmethod
    def get_status_payload(task_id) -> dict:
        escrow = EscrowLifecycleService.get_escrow_for_task(task_id)
        if not escrow:
            return {'task_id': str(task_id), 'escrow': None}
        payment = escrow.payment
        return {
            'task_id': str(task_id),
            'escrow': {
                'id': str(escrow.id),
                'status': escrow.status,
                'amount': str(escrow.amount),
                'platform_fee': str(escrow.platform_fee),
                'net_amount': str(escrow.net_amount),
                'currency': escrow.currency,
                'funding_method': escrow.funding_method,
                'locked_at': escrow.locked_at,
                'released_at': escrow.released_at,
                'refunded_at': escrow.refunded_at,
                'auto_release_at': escrow.auto_release_at,
            },
            'payment': {
                'id': str(payment.id),
                'status': payment.status,
                'payment_method': payment.payment_method,
                'is_escrowed': payment.is_escrowed,
            },
        }
