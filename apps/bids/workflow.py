"""
Bid Workflow Orchestration Service
Handles the complete workflow from bid acceptance to task completion
"""
from django.db import transaction
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from decimal import Decimal
import logging

from .models import Bid
from apps.tasks.models import Task, TaskActivity
from apps.chat.conversation_resolver import get_or_create_conversation
from apps.notifications.services import NotificationService
from apps.payments.services import EscrowService
from apps.users.models import User

logger = logging.getLogger(__name__)


class BidWorkflowService:
    """
    Orchestrates the complete bid workflow following Airtasker patterns.
    
    Workflow Stages:
    1. Bid Submission
    2. Bid Acceptance (triggers escrow, assignment, notifications)
    3. Task Execution
    4. Task Completion
    5. Payment Release
    6. Review Exchange
    """
    
    @staticmethod
    @transaction.atomic
    def accept_bid(bid_id: str, task_owner: User) -> dict:
        """
        Complete workflow for accepting a bid.
        
        Steps:
        1. Validate bid and task status
        2. Create escrow payment
        3. Assign provider to task
        4. Update task status to 'assigned'
        5. Reject all other pending bids
        6. Create private conversation
        7. Send notifications to all parties
        8. Create activity logs
        
        Args:
            bid_id: UUID of the bid to accept
            task_owner: User accepting the bid (must be task owner)
            
        Returns:
            dict: {
                'bid': Bid object,
                'task': Task object,
                'payment': Payment object,
                'conversation': Conversation object
            }
            
        Raises:
            ValidationError: If bid/task status invalid
            PermissionDenied: If user is not task owner
        """
        try:
            # 1. Validate bid and task
            bid = Bid.objects.select_related('task', 'tasker').get(id=bid_id)
            task = bid.task
            
            # Permission check
            if task.owner != task_owner:
                raise PermissionDenied("Only task owner can accept bids")
            
            # Status validation
            if bid.status != 'pending':
                raise ValidationError(f"Cannot accept bid with status: {bid.status}")
            
            if task.status not in ['open', 'draft']:
                raise ValidationError(f"Cannot accept bid for task with status: {task.status}")
            
            # Check if task already has accepted bid
            if task.bids.filter(status='accepted').exists():
                raise ValidationError("Task already has an accepted bid")
            
            logger.info(f"Accepting bid {bid_id} for task {task.id}")

            # 2. Validate wallet balance and create escrow (hold funds from owner wallet)
            EscrowService.validate_owner_wallet_for_acceptance(bid)
            payment = EscrowService.create_escrow_on_bid_acceptance(bid)
            logger.info(f"Created escrow payment {payment.id} for {payment.currency} {payment.amount}")
            
            # 3. Update bid status
            bid.status = 'accepted'
            bid.accepted_at = timezone.now()
            bid.save()
            
            # 4. Assign provider to task and update status
            task.assigned_tasker = bid.tasker
            task.status = 'funded'
            task.save(update_fields=['assigned_tasker', 'status'])
            
            # 5. Reject all other pending bids
            other_bids_qs = task.bids.filter(status='pending').exclude(id=bid.id)
            rejected_bids = list(other_bids_qs.select_related('tasker'))
            rejected_count = other_bids_qs.update(
                status='rejected',
                rejected_at=timezone.now(),
                rejection_reason='Another bid was accepted'
            )
            logger.info(f"Rejected {rejected_count} other bids")
            
            # 6. Reuse or create private conversation (one thread per bid/task)
            conversation, created = get_or_create_conversation(
                task=task,
                bid=bid,
                participant_users=[task.owner, bid.tasker],
            )
            logger.info(
                "%s conversation %s",
                "Created" if created else "Reused",
                conversation.id,
            )
            
            # 7. Create activity logs
            TaskActivity.objects.create(
                task=task,
                activity_type='bid_accepted',
                actor=task_owner,
                description=f"Accepted bid from {bid.tasker.get_full_name()} for ${bid.amount}",
                metadata={
                    'bid_id': str(bid.id),
                    'amount': str(bid.amount),
                    'tasker_id': str(bid.tasker.id)
                }
            )
            
            TaskActivity.objects.create(
                task=task,
                activity_type='assigned',
                actor=task_owner,
                description=f"Task assigned to {bid.tasker.get_full_name()}",
                metadata={
                    'tasker_id': str(bid.tasker.id)
                }
            )
            
            # 8. Send notifications after DB commit (keeps SQLite write lock short)
            accepted_tasker = bid.tasker
            rejected_payloads = [
                (rb.tasker, rb, str(rb.id)) for rb in rejected_bids
            ]
            conv_id = str(conversation.id)
            task_id_str = str(task.id)
            bid_id_str = str(bid.id)
            payment_id_str = str(payment.id)
            task_title = task.title
            owner_name = task_owner.get_full_name()
            tasker_name = accepted_tasker.get_full_name()
            pay_currency = payment.currency
            pay_amount = payment.amount
            bid_amount = bid.amount

            def send_acceptance_notifications():
                try:
                    NotificationService.send_notification(
                        user=accepted_tasker,
                        sender=task_owner,
                        notification_type='bid_accepted',
                        title='Your bid was accepted',
                        message=(
                            f'{owner_name} accepted your bid of ${bid_amount} '
                            f'for "{task_title}". Payment is now in escrow.'
                        ),
                        related_object=bid,
                        data={
                            'task_id': task_id_str,
                            'bid_id': bid_id_str,
                            'conversation_id': conv_id,
                            'action_url': f'/message?conversation={conv_id}',
                        },
                    )
                    for rej_tasker, rej_bid, rej_bid_id in rejected_payloads:
                        NotificationService.send_notification(
                            user=rej_tasker,
                            sender=task_owner,
                            notification_type='bid_rejected',
                            title='Bid not selected',
                            message=(
                                f'Your bid for "{task_title}" was not selected. '
                                'The task owner chose another provider.'
                            ),
                            related_object=rej_bid,
                            data={'task_id': task_id_str, 'bid_id': rej_bid_id},
                        )
                    NotificationService.send_notification(
                        user=task_owner,
                        sender=accepted_tasker,
                        notification_type='bid_accepted',
                        title='Bid accepted successfully',
                        message=(
                            f'You accepted {tasker_name}\'s bid. Payment of '
                            f'{pay_currency} {pay_amount} is now in escrow.'
                        ),
                        related_object=task,
                        data={
                            'task_id': task_id_str,
                            'bid_id': bid_id_str,
                            'payment_id': payment_id_str,
                            'conversation_id': conv_id,
                            'action_url': f'/message?conversation={conv_id}',
                        },
                    )
                except Exception as notify_err:
                    logger.error(
                        f"Post-accept notifications failed: {notify_err}",
                        exc_info=True,
                    )

            transaction.on_commit(send_acceptance_notifications)

            logger.info(f"Bid acceptance workflow completed successfully for bid {bid_id}")
            
            return {
                'bid': bid,
                'task': task,
                'payment': payment,
                'conversation': conversation,
                'rejected_bids_count': rejected_count
            }
            
        except Bid.DoesNotExist:
            logger.error(f"Bid {bid_id} not found")
            raise ValidationError("Bid not found")
        except Exception as e:
            logger.error(f"Error in bid acceptance workflow: {str(e)}", exc_info=True)
            raise
    
    @staticmethod
    @transaction.atomic
    def reject_bid(bid_id: str, task_owner: User, reason: str = None) -> Bid:
        """
        Reject a bid.
        
        Args:
            bid_id: UUID of the bid to reject
            task_owner: User rejecting the bid
            reason: Optional rejection reason
            
        Returns:
            Bid: Updated bid object
        """
        try:
            bid = Bid.objects.select_related('task', 'tasker').get(id=bid_id)
            task = bid.task
            
            # Permission check
            if task.owner != task_owner:
                raise PermissionDenied("Only task owner can reject bids")
            
            # Status validation
            if bid.status != 'pending':
                raise ValidationError(f"Cannot reject bid with status: {bid.status}")
            
            # Update bid
            bid.status = 'rejected'
            bid.rejected_at = timezone.now()
            bid.rejection_reason = reason or 'Bid not selected'
            bid.save()
            
            # Create activity
            TaskActivity.objects.create(
                task=task,
                activity_type='bid_rejected',
                actor=task_owner,
                description=f"Rejected bid from {bid.tasker.get_full_name()}",
                metadata={
                    'bid_id': str(bid.id),
                    'reason': reason
                }
            )
            
            # Notify bidder
            NotificationService.send_notification(
                user=bid.tasker,
                notification_type='bid_rejected',
                title='Bid Not Selected',
                message=f'Your bid for "{task.title}" was not selected.',
                related_object=bid,
                data={
                    'task_id': str(task.id),
                    'bid_id': str(bid.id),
                    'reason': reason
                }
            )
            
            logger.info(f"Bid {bid_id} rejected successfully")
            return bid
            
        except Bid.DoesNotExist:
            logger.error(f"Bid {bid_id} not found")
            raise ValidationError("Bid not found")
    
    @staticmethod
    @transaction.atomic
    def withdraw_bid(bid_id: str, tasker: User, reason: str = None) -> Bid:
        """
        Withdraw a bid (tasker cancels their own bid).
        
        Args:
            bid_id: UUID of the bid to withdraw
            tasker: User withdrawing the bid
            reason: Optional withdrawal reason
            
        Returns:
            Bid: Updated bid object
        """
        try:
            bid = Bid.objects.select_related('task', 'tasker').get(id=bid_id)
            
            # Permission check
            if bid.tasker != tasker:
                raise PermissionDenied("Only bid owner can withdraw their bid")
            
            # Status validation
            if bid.status != 'pending':
                raise ValidationError(f"Cannot withdraw bid with status: {bid.status}")
            
            # Update bid
            bid.status = 'withdrawn'
            bid.withdrawn_at = timezone.now()
            bid.withdrawal_reason = reason or 'Bid withdrawn by tasker'
            bid.save()
            
            # Create activity
            TaskActivity.objects.create(
                task=bid.task,
                activity_type='bid_withdrawn',
                actor=tasker,
                description=f"{tasker.get_full_name()} withdrew their bid",
                metadata={
                    'bid_id': str(bid.id),
                    'reason': reason
                }
            )
            
            # Notify task owner
            NotificationService.send_notification(
                user=bid.task.owner,
                notification_type='bid_withdrawn',
                title='Bid Withdrawn',
                message=f'{tasker.get_full_name()} withdrew their bid for "{bid.task.title}".',
                related_object=bid,
                data={
                    'task_id': str(bid.task.id),
                    'bid_id': str(bid.id)
                }
            )
            
            logger.info(f"Bid {bid_id} withdrawn successfully")
            return bid
            
        except Bid.DoesNotExist:
            logger.error(f"Bid {bid_id} not found")
            raise ValidationError("Bid not found")
    
    @staticmethod
    def get_bid_statistics(task_id: str) -> dict:
        """
        Get statistics for all bids on a task.
        
        Args:
            task_id: UUID of the task
            
        Returns:
            dict: Bid statistics
        """
        from django.db.models import Avg, Min, Max, Count
        
        bids = Bid.objects.filter(task_id=task_id, status='pending')
        
        if not bids.exists():
            return {
                'total_bids': 0,
                'average_bid': None,
                'lowest_bid': None,
                'highest_bid': None,
                'best_rated_provider': None
            }
        
        stats = bids.aggregate(
            total=Count('id'),
            avg_amount=Avg('amount'),
            min_amount=Min('amount'),
            max_amount=Max('amount')
        )
        
        # Get best rated provider
        best_rated_bid = bids.select_related('tasker').order_by(
            '-tasker__average_rating',
            'amount'
        ).first()
        
        return {
            'total_bids': stats['total'],
            'average_bid': float(stats['avg_amount']) if stats['avg_amount'] else None,
            'lowest_bid': float(stats['min_amount']) if stats['min_amount'] else None,
            'highest_bid': float(stats['max_amount']) if stats['max_amount'] else None,
            'best_rated_provider': {
                'id': str(best_rated_bid.tasker.id),
                'name': best_rated_bid.tasker.get_full_name(),
                'rating': float(best_rated_bid.tasker.average_rating),
                'bid_amount': float(best_rated_bid.amount)
            } if best_rated_bid else None
        }
