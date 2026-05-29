"""
Bid service layer for business logic.
Handles bid acceptance, rejection, and workflow orchestration.
"""
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from typing import Optional, Dict, Any
import logging

from .models import Bid
from apps.tasks.models import Task
from apps.notifications.models import Notification
from apps.analytics.models import ActivityLog

logger = logging.getLogger(__name__)


class BidService:
    """Service class for bid operations."""
    
    @staticmethod
    @transaction.atomic
    def accept_bid(bid_id: str, accepted_by_user) -> Dict[str, Any]:
        """
        Accept a bid and orchestrate the complete workflow.
        
        This method:
        1. Validates the bid can be accepted
        2. Accepts the bid
        3. Assigns task to tasker
        4. Rejects all other pending bids
        5. Creates activity logs
        6. Sends notifications
        7. Initiates escrow (if payment configured)
        
        Args:
            bid_id: UUID of the bid to accept
            accepted_by_user: User accepting the bid (must be task owner)
        
        Returns:
            Dict with success status and details
        
        Raises:
            ValidationError: If bid cannot be accepted
        """
        try:
            # Get bid with related data
            bid = Bid.objects.select_related(
                'task', 'tasker', 'task__owner'
            ).get(id=bid_id)
            
            # Validate user is task owner
            if bid.task.owner != accepted_by_user:
                raise ValidationError("Only task owner can accept bids")
            
            # Validate bid status
            if bid.status != 'pending':
                raise ValidationError(f"Cannot accept bid with status: {bid.status}")
            
            # Validate task status
            if bid.task.status != 'open':
                raise ValidationError(f"Cannot accept bid for task with status: {bid.task.status}")
            
            # Accept the bid
            bid.status = 'accepted'
            bid.accepted_at = timezone.now()
            bid.save(update_fields=['status', 'accepted_at'])
            
            # Assign task to tasker
            bid.task.assigned_tasker = bid.tasker
            bid.task.status = 'assigned'
            bid.task.save(update_fields=['assigned_tasker', 'status'])
            
            # Reject all other pending bids
            rejected_count = Bid.objects.filter(
                task=bid.task,
                status='pending'
            ).exclude(id=bid.id).update(
                status='rejected',
                rejected_at=timezone.now(),
                rejection_reason='Another bid was accepted'
            )
            
            # Create activity log
            ActivityLog.objects.create(
                task=bid.task,
                actor=accepted_by_user,
                activity_type='BID_ACCEPTED',
                description=f"Bid accepted from {bid.tasker.get_full_name()}",
                metadata={
                    'bid_id': str(bid.id),
                    'bid_amount': float(bid.amount),
                    'tasker_id': str(bid.tasker.id),
                    'rejected_bids_count': rejected_count
                }
            )
            
            # Send notification to tasker (bid accepted)
            Notification.objects.create(
                recipient=bid.tasker,
                notification_type='bid_accepted',
                title='Your Offer Was Accepted! 🎉',
                message=f'Your offer for "{bid.task.title}" has been accepted. You can now start working on the task.',
                related_object=bid,
                action_url=f'/tasks/{bid.task.id}',
                metadata={
                    'task_id': str(bid.task.id),
                    'bid_id': str(bid.id),
                    'amount': float(bid.amount)
                }
            )
            
            # Send notifications to rejected bidders
            rejected_bids = Bid.objects.filter(
                task=bid.task,
                status='rejected',
                rejection_reason='Another bid was accepted'
            ).select_related('tasker')
            
            for rejected_bid in rejected_bids:
                Notification.objects.create(
                    recipient=rejected_bid.tasker,
                    notification_type='bid_rejected',
                    title='Offer Not Selected',
                    message=f'Unfortunately, your offer for "{bid.task.title}" was not selected. Keep trying!',
                    related_object=rejected_bid,
                    metadata={
                        'task_id': str(bid.task.id),
                        'bid_id': str(rejected_bid.id)
                    }
                )
            
            # TODO: Initiate escrow payment
            # escrow_service.create_escrow(bid)
            
            logger.info(
                f"Bid {bid.id} accepted successfully. "
                f"Task {bid.task.id} assigned to {bid.tasker.id}. "
                f"{rejected_count} other bids rejected."
            )
            
            return {
                'success': True,
                'message': 'Bid accepted successfully',
                'data': {
                    'bid_id': str(bid.id),
                    'task_id': str(bid.task.id),
                    'tasker_id': str(bid.tasker.id),
                    'rejected_bids_count': rejected_count
                }
            }
            
        except Bid.DoesNotExist:
            raise ValidationError("Bid not found")
        except Exception as e:
            logger.error(f"Error accepting bid {bid_id}: {str(e)}")
            raise
    
    @staticmethod
    @transaction.atomic
    def reject_bid(bid_id: str, rejected_by_user, reason: str = '') -> Dict[str, Any]:
        """
        Reject a bid.
        
        Args:
            bid_id: UUID of the bid to reject
            rejected_by_user: User rejecting the bid (must be task owner)
            reason: Optional rejection reason
        
        Returns:
            Dict with success status
        
        Raises:
            ValidationError: If bid cannot be rejected
        """
        try:
            bid = Bid.objects.select_related('task', 'tasker').get(id=bid_id)
            
            # Validate user is task owner
            if bid.task.owner != rejected_by_user:
                raise ValidationError("Only task owner can reject bids")
            
            # Validate bid status
            if bid.status != 'pending':
                raise ValidationError(f"Cannot reject bid with status: {bid.status}")
            
            # Reject the bid
            bid.status = 'rejected'
            bid.rejected_at = timezone.now()
            bid.rejection_reason = reason
            bid.save(update_fields=['status', 'rejected_at', 'rejection_reason'])
            
            # Create activity log
            ActivityLog.objects.create(
                task=bid.task,
                actor=rejected_by_user,
                activity_type='BID_REJECTED',
                description=f"Bid rejected from {bid.tasker.get_full_name()}",
                metadata={
                    'bid_id': str(bid.id),
                    'reason': reason
                }
            )
            
            # Send notification to tasker
            Notification.objects.create(
                recipient=bid.tasker,
                notification_type='bid_rejected',
                title='Offer Not Selected',
                message=f'Your offer for "{bid.task.title}" was not selected.',
                related_object=bid,
                metadata={
                    'task_id': str(bid.task.id),
                    'bid_id': str(bid.id),
                    'reason': reason
                }
            )
            
            logger.info(f"Bid {bid.id} rejected successfully")
            
            return {
                'success': True,
                'message': 'Bid rejected successfully'
            }
            
        except Bid.DoesNotExist:
            raise ValidationError("Bid not found")
        except Exception as e:
            logger.error(f"Error rejecting bid {bid_id}: {str(e)}")
            raise
    
    @staticmethod
    @transaction.atomic
    def withdraw_bid(bid_id: str, withdrawn_by_user, reason: str = '') -> Dict[str, Any]:
        """
        Withdraw a bid (by the bidder).
        
        Args:
            bid_id: UUID of the bid to withdraw
            withdrawn_by_user: User withdrawing the bid (must be bidder)
            reason: Optional withdrawal reason
        
        Returns:
            Dict with success status
        
        Raises:
            ValidationError: If bid cannot be withdrawn
        """
        try:
            bid = Bid.objects.select_related('task', 'tasker').get(id=bid_id)
            
            # Validate user is the bidder
            if bid.tasker != withdrawn_by_user:
                raise ValidationError("Only the bidder can withdraw their bid")
            
            # Validate bid status
            if bid.status != 'pending':
                raise ValidationError(f"Cannot withdraw bid with status: {bid.status}")
            
            # Withdraw the bid
            bid.status = 'withdrawn'
            bid.withdrawn_at = timezone.now()
            bid.withdrawal_reason = reason
            bid.save(update_fields=['status', 'withdrawn_at', 'withdrawal_reason'])
            
            # Create activity log
            ActivityLog.objects.create(
                task=bid.task,
                actor=withdrawn_by_user,
                activity_type='BID_WITHDRAWN',
                description=f"Bid withdrawn by {bid.tasker.get_full_name()}",
                metadata={
                    'bid_id': str(bid.id),
                    'reason': reason
                }
            )
            
            # Send notification to task owner
            Notification.objects.create(
                recipient=bid.task.owner,
                notification_type='bid_withdrawn',
                title='Offer Withdrawn',
                message=f'{bid.tasker.get_full_name()} withdrew their offer for "{bid.task.title}".',
                related_object=bid,
                metadata={
                    'task_id': str(bid.task.id),
                    'bid_id': str(bid.id)
                }
            )
            
            logger.info(f"Bid {bid.id} withdrawn successfully")
            
            return {
                'success': True,
                'message': 'Bid withdrawn successfully'
            }
            
        except Bid.DoesNotExist:
            raise ValidationError("Bid not found")
        except Exception as e:
            logger.error(f"Error withdrawing bid {bid_id}: {str(e)}")
            raise
    
    @staticmethod
    def get_task_bid_statistics(task_id: str) -> Dict[str, Any]:
        """
        Get statistics for all bids on a task.
        
        Args:
            task_id: UUID of the task
        
        Returns:
            Dict with bid statistics
        """
        from django.db.models import Count, Avg, Min, Max
        
        bids = Bid.objects.filter(task_id=task_id, status='pending')
        
        if not bids.exists():
            return {
                'total_offers': 0,
                'average_offer': 0,
                'lowest_offer': 0,
                'highest_offer': 0,
                'best_rated_provider': None
            }
        
        stats = bids.aggregate(
            total=Count('id'),
            avg_amount=Avg('amount'),
            min_amount=Min('amount'),
            max_amount=Max('amount')
        )
        
        # Get best rated provider
        best_rated_bid = bids.select_related('tasker', 'tasker__profile').order_by(
            '-tasker__profile__rating', 'amount'
        ).first()
        
        return {
            'total_offers': stats['total'],
            'average_offer': float(stats['avg_amount'] or 0),
            'lowest_offer': float(stats['min_amount'] or 0),
            'highest_offer': float(stats['max_amount'] or 0),
            'best_rated_provider': {
                'id': str(best_rated_bid.tasker.id),
                'name': best_rated_bid.tasker.get_full_name(),
                'rating': best_rated_bid.tasker.profile.rating,
                'reviews_count': best_rated_bid.tasker.profile.reviews_count,
                'bid_amount': float(best_rated_bid.amount)
            } if best_rated_bid else None
        }
    
    @staticmethod
    def check_duplicate_bid(task_id: str, tasker_id: str) -> bool:
        """
        Check if user already has a pending bid on this task.
        
        Args:
            task_id: UUID of the task
            tasker_id: UUID of the tasker
        
        Returns:
            True if duplicate exists, False otherwise
        """
        return Bid.objects.filter(
            task_id=task_id,
            tasker_id=tasker_id,
            status='pending'
        ).exists()
    
    @staticmethod
    def validate_bid_creation(task_id: str, tasker_id: str) -> Dict[str, Any]:
        """
        Validate if a bid can be created.
        
        Args:
            task_id: UUID of the task
            tasker_id: UUID of the tasker
        
        Returns:
            Dict with validation result
        """
        from apps.tasks.models import Task
        
        try:
            task = Task.objects.get(id=task_id)
            
            # Check if task is open
            if task.status != 'open':
                return {
                    'valid': False,
                    'error': 'Task is not open for bids'
                }
            
            # Check if task owner is trying to bid
            if str(task.owner.id) == str(tasker_id):
                return {
                    'valid': False,
                    'error': 'You cannot bid on your own task'
                }
            
            # Check for duplicate bid
            if BidService.check_duplicate_bid(task_id, tasker_id):
                return {
                    'valid': False,
                    'error': 'You already have a pending bid on this task'
                }
            
            # Check if bids are allowed
            if not task.allow_bids:
                return {
                    'valid': False,
                    'error': 'This task is not accepting bids'
                }
            
            return {
                'valid': True,
                'error': None
            }
            
        except Task.DoesNotExist:
            return {
                'valid': False,
                'error': 'Task not found'
            }


# Singleton instance
bid_service = BidService()
