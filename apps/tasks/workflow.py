"""
Task Completion Workflow Service
Handles task execution, completion requests, approvals, and revisions
"""
from django.db import transaction
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from decimal import Decimal
import logging

from .models import Task, TaskActivity
from apps.notifications.services import NotificationService
from apps.payments.services import EscrowService
from apps.payments.escrow_lifecycle import EscrowLifecycleService
from apps.reviews.services import ReviewService
from apps.users.models import User

logger = logging.getLogger(__name__)


class TaskCompletionService:
    """
    Orchestrates task completion workflow.
    
    Workflow:
    1. Provider starts task
    2. Provider updates progress
    3. Provider requests completion
    4. Owner approves/requests revision
    5. Payment released on approval
    6. Review invitations sent
    """
    
    @staticmethod
    @transaction.atomic
    def start_task(task_id: str, provider: User) -> Task:
        """
        Provider starts working on assigned task.
        
        Args:
            task_id: UUID of the task
            provider: User starting the task
            
        Returns:
            Task: Updated task object
        """
        try:
            task = Task.objects.select_related('owner', 'assigned_tasker').get(id=task_id)
            
            # Validation
            if task.assigned_tasker != provider:
                raise PermissionDenied("Only assigned provider can start this task")
            
            if task.status not in ('assigned', 'funded'):
                raise ValidationError(f"Cannot start task with status: {task.status}")
            
            # Update task
            task.status = 'in_progress'
            if hasattr(task, 'started_at'):
                task.started_at = timezone.now()
                task.save()
            else:
                task.start_date = timezone.now()
                task.save(update_fields=['status', 'start_date'])
            EscrowLifecycleService.on_task_started(task, actor=provider)
            
            # Create activity
            TaskActivity.objects.create(
                task=task,
                activity_type='started',
                actor=provider,
                description=f"{provider.get_full_name()} started working on the task"
            )
            
            # Notify task owner
            NotificationService.send_notification(
                user=task.owner,
                notification_type='task_started',
                title='Task Started',
                message=f'{provider.get_full_name()} has started working on "{task.title}".',
                related_object=task,
                data={'task_id': str(task.id)}
            )
            
            logger.info(f"Task {task_id} started by provider {provider.id}")
            return task
            
        except Task.DoesNotExist:
            logger.error(f"Task {task_id} not found")
            raise ValidationError("Task not found")
    
    @staticmethod
    @transaction.atomic
    def update_progress(
        task_id: str,
        provider: User,
        progress_percentage: int,
        description: str,
        proof_files: list = None
    ) -> dict:
        """
        Provider updates task progress.
        
        Args:
            task_id: UUID of the task
            provider: User updating progress
            progress_percentage: Progress (0-100)
            description: Progress description
            proof_files: Optional list of file URLs
            
        Returns:
            dict: Progress update details
        """
        try:
            task = Task.objects.select_related('owner', 'assigned_tasker').get(id=task_id)
            
            # Validation
            if task.assigned_tasker != provider:
                raise PermissionDenied("Only assigned provider can update progress")
            
            if task.status != 'in_progress':
                raise ValidationError(f"Cannot update progress for task with status: {task.status}")
            
            if not (0 <= progress_percentage <= 100):
                raise ValidationError("Progress must be between 0 and 100")
            
            # Create progress record (assuming model exists or using metadata)
            progress_data = {
                'percentage': progress_percentage,
                'description': description,
                'proof_files': proof_files or [],
                'timestamp': timezone.now().isoformat()
            }
            
            # Create activity
            TaskActivity.objects.create(
                task=task,
                activity_type='progress_updated',
                actor=provider,
                description=f"Progress updated to {progress_percentage}%: {description}",
                metadata=progress_data
            )
            
            # Notify task owner
            NotificationService.send_notification(
                user=task.owner,
                notification_type='task_progress_updated',
                title='Task Progress Updated',
                message=f'{provider.get_full_name()} updated progress to {progress_percentage}% on "{task.title}".',
                related_object=task,
                data={
                    'task_id': str(task.id),
                    'progress': progress_percentage
                }
            )
            
            logger.info(f"Progress updated for task {task_id}: {progress_percentage}%")
            return progress_data
            
        except Task.DoesNotExist:
            logger.error(f"Task {task_id} not found")
            raise ValidationError("Task not found")
    
    @staticmethod
    @transaction.atomic
    def request_completion(
        task_id: str,
        provider: User,
        completion_notes: str,
        proof_files: list = None
    ) -> Task:
        """
        Provider requests task completion.
        
        Args:
            task_id: UUID of the task
            provider: User requesting completion
            completion_notes: Completion description
            proof_files: Optional list of proof file URLs
            
        Returns:
            Task: Updated task object
        """
        try:
            task = Task.objects.select_related('owner', 'assigned_tasker').get(id=task_id)
            
            # Validation
            if task.assigned_tasker != provider:
                raise PermissionDenied("Only assigned provider can request completion")
            
            if task.status != 'in_progress':
                raise ValidationError(f"Cannot request completion for task with status: {task.status}")
            
            # Update task
            task.status = 'pending_approval'
            update_fields = ['status']
            if hasattr(task, 'completion_requested_at'):
                task.completion_requested_at = timezone.now()
                update_fields.append('completion_requested_at')
            task.save(update_fields=update_fields)
            EscrowLifecycleService.on_completion_submitted(task, actor=provider)
            
            # Create activity
            TaskActivity.objects.create(
                task=task,
                activity_type='completion_requested',
                actor=provider,
                description=f"{provider.get_full_name()} requested task completion",
                metadata={
                    'completion_notes': completion_notes,
                    'proof_files': proof_files or []
                }
            )
            
            # Notify task owner
            NotificationService.send_notification(
                user=task.owner,
                notification_type='task_completion_requested',
                title='Task Completion Requested',
                message=f'{provider.get_full_name()} has completed "{task.title}" and is requesting approval.',
                related_object=task,
                data={
                    'task_id': str(task.id),
                    'completion_notes': completion_notes,
                    'proof_files': proof_files or [],
                    'action_url': f'/tasks/{task.id}/review-completion'
                }
            )
            
            logger.info(f"Completion requested for task {task_id}")
            return task
            
        except Task.DoesNotExist:
            logger.error(f"Task {task_id} not found")
            raise ValidationError("Task not found")
    
    @staticmethod
    @transaction.atomic
    def approve_completion(task_id: str, owner: User) -> dict:
        """
        Task owner approves completion.
        
        This triggers:
        1. Task status update to 'completed'
        2. Escrow payment release
        3. Notifications to provider
        4. Review invitation emails
        
        Args:
            task_id: UUID of the task
            owner: User approving completion
            
        Returns:
            dict: Completion details including payment info
        """
        try:
            task = Task.objects.select_related('owner', 'assigned_tasker').get(id=task_id)
            
            # Validation
            if task.owner != owner:
                raise PermissionDenied("Only task owner can approve completion")
            
            if task.status != 'pending_approval':
                raise ValidationError(f"Cannot approve task with status: {task.status}")
            
            # Update task
            task.status = 'completed'
            update_fields = ['status']
            if hasattr(task, 'completed_at'):
                task.completed_at = timezone.now()
                update_fields.append('completed_at')
            else:
                task.completion_date = timezone.now()
                update_fields.append('completion_date')
            task.save(update_fields=update_fields)

            EscrowLifecycleService.on_task_completed(task, actor=owner)

            # Release escrow payment (platform fees deducted, credit tasker wallet)
            payment = EscrowLifecycleService.release_escrow(task, actor=owner)
            
            # Create activity
            TaskActivity.objects.create(
                task=task,
                activity_type='completed',
                actor=owner,
                description=(
                    f"Task completed — {payment.net_amount} {payment.currency} released to tasker "
                    f"(platform fee {payment.platform_fee} {payment.currency})"
                ),
                metadata={
                    'payment_id': str(payment.id),
                    'amount': str(payment.net_amount)
                }
            )
            
            # Notify provider
            NotificationService.send_notification(
                user=task.assigned_tasker,
                notification_type='task_approved',
                title='🎉 Task Approved!',
                message=(
                    f'Your work on "{task.title}" has been approved! '
                    f'{payment.net_amount} {payment.currency} has been credited to your wallet '
                    f'(after {payment.platform_fee} {payment.currency} platform fee).'
                ),
                related_object=task,
                data={
                    'task_id': str(task.id),
                    'payment_id': str(payment.id),
                    'amount': str(payment.net_amount),
                    'action_url': f'/wallet'
                }
            )
            
            # Send review invitations
            ReviewService.send_review_invitations(task)
            
            logger.info(f"Task {task_id} approved and completed. Payment ${payment.net_amount} released.")
            
            return {
                'task': task,
                'payment': payment,
                'net_amount': float(payment.net_amount)
            }
            
        except Task.DoesNotExist:
            logger.error(f"Task {task_id} not found")
            raise ValidationError("Task not found")
    
    @staticmethod
    @transaction.atomic
    def request_revision(
        task_id: str,
        owner: User,
        revision_notes: str
    ) -> Task:
        """
        Task owner requests revisions.
        
        Args:
            task_id: UUID of the task
            owner: User requesting revision
            revision_notes: Description of required changes
            
        Returns:
            Task: Updated task object
        """
        try:
            task = Task.objects.select_related('owner', 'assigned_tasker').get(id=task_id)
            
            # Validation
            if task.owner != owner:
                raise PermissionDenied("Only task owner can request revisions")
            
            if task.status != 'pending_approval':
                raise ValidationError(f"Cannot request revision for task with status: {task.status}")
            
            # Update task back to in_progress
            task.status = 'in_progress'
            task.save(update_fields=['status'])
            EscrowLifecycleService.on_task_started(task, actor=owner)

            # Create activity
            TaskActivity.objects.create(
                task=task,
                activity_type='revision_requested',
                actor=owner,
                description=f"{owner.get_full_name()} requested revisions",
                metadata={
                    'revision_notes': revision_notes
                }
            )
            
            # Notify provider
            NotificationService.send_notification(
                user=task.assigned_tasker,
                notification_type='revision_requested',
                title='Revision Requested',
                message=f'{owner.get_full_name()} has requested revisions on "{task.title}".',
                related_object=task,
                data={
                    'task_id': str(task.id),
                    'revision_notes': revision_notes,
                    'action_url': f'/tasks/{task.id}'
                }
            )
            
            logger.info(f"Revision requested for task {task_id}")
            return task
            
        except Task.DoesNotExist:
            logger.error(f"Task {task_id} not found")
            raise ValidationError("Task not found")
    
    @staticmethod
    @transaction.atomic
    def cancel_task(
        task_id: str,
        user: User,
        cancellation_reason: str
    ) -> dict:
        """
        Cancel a task and handle refunds if applicable.
        
        Args:
            task_id: UUID of the task
            user: User cancelling the task
            cancellation_reason: Reason for cancellation
            
        Returns:
            dict: Cancellation details including refund info
        """
        try:
            task = Task.objects.select_related('owner', 'assigned_tasker').get(id=task_id)
            
            # Permission check
            if task.owner != user and task.assigned_tasker != user:
                raise PermissionDenied("Only task owner or assigned provider can cancel")
            
            # Status validation
            if task.status in ['completed', 'cancelled']:
                raise ValidationError(f"Cannot cancel task with status: {task.status}")
            
            # Handle refund if payment exists
            refund_info = None
            if task.status in ['assigned', 'funded', 'in_progress', 'pending_approval']:
                refund_info = EscrowService.refund_escrow_on_cancellation(task, cancellation_reason)
            
            # Update task
            task.status = 'cancelled'
            task.cancelled_at = timezone.now()
            task.cancellation_reason = cancellation_reason
            task.cancelled_by = user
            task.save()

            from apps.rules.services import ModerationService
            ModerationService.on_task_cancelled(user)
            
            # Create activity
            TaskActivity.objects.create(
                task=task,
                activity_type='cancelled',
                actor=user,
                description=f"Task cancelled by {user.get_full_name()}: {cancellation_reason}",
                metadata={
                    'reason': cancellation_reason,
                    'refund_issued': refund_info is not None
                }
            )
            
            # Notify relevant parties
            if task.assigned_tasker and task.assigned_tasker != user:
                NotificationService.send_notification(
                    user=task.assigned_tasker,
                    notification_type='task_cancelled',
                    title='Task Cancelled',
                    message=f'The task "{task.title}" has been cancelled.',
                    related_object=task,
                    data={
                        'task_id': str(task.id),
                        'reason': cancellation_reason
                    }
                )
            
            if task.owner != user:
                NotificationService.send_notification(
                    user=task.owner,
                    notification_type='task_cancelled',
                    title='Task Cancelled',
                    message=f'The task "{task.title}" has been cancelled.',
                    related_object=task,
                    data={
                        'task_id': str(task.id),
                        'reason': cancellation_reason,
                        'refund_amount': str(refund_info['refund_amount']) if refund_info else None
                    }
                )
            
            logger.info(f"Task {task_id} cancelled by user {user.id}")
            
            return {
                'task': task,
                'refund_info': refund_info
            }
            
        except Task.DoesNotExist:
            logger.error(f"Task {task_id} not found")
            raise ValidationError("Task not found")
