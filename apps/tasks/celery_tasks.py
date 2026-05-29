"""
Celery Tasks for Task Management
Background jobs for task lifecycle automation
"""
from celery import shared_task
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def auto_complete_task(self):
    """
    Auto-complete tasks that have passed their deadline.
    
    Workflow:
    1. Find tasks with status='in_progress' and deadline passed
    2. Update status to 'completed'
    3. Trigger escrow release
    4. Send notifications to both parties
    
    Runs: Every 30 minutes (configured in celery.py)
    """
    from .models import Task
    from apps.notifications.services import NotificationService
    
    try:
        # Find tasks that should be auto-completed
        now = timezone.now()
        expired_tasks = Task.objects.filter(
            status='in_progress',
            deadline__lt=now,
            auto_complete_enabled=True
        )
        
        completed_count = 0
        
        for task in expired_tasks:
            try:
                # Update task status
                task.status = 'completed'
                task.completed_at = now
                task.save()
                
                # Send notification to task owner
                NotificationService.send_notification(
                    user=task.owner,
                    notification_type='task_completed',
                    title='Task Auto-Completed',
                    message=f'Your task "{task.title}" has been automatically completed after the deadline.',
                    related_object=task,
                    priority='normal'
                )
                
                # Send notification to tasker
                if task.assigned_to:
                    NotificationService.send_notification(
                        user=task.assigned_to,
                        notification_type='task_completed',
                        title='Task Auto-Completed',
                        message=f'Task "{task.title}" has been automatically completed. Payment will be released soon.',
                        related_object=task,
                        priority='normal'
                    )
                
                completed_count += 1
                logger.info(f"Auto-completed task {task.id}: {task.title}")
                
            except Exception as e:
                logger.error(f"Error auto-completing task {task.id}: {e}")
                continue
        
        logger.info(f"Auto-completed {completed_count} tasks")
        return {
            'success': True,
            'completed_count': completed_count
        }
        
    except Exception as exc:
        logger.error(f"Error in auto_complete_task: {exc}")
        raise self.retry(exc=exc, countdown=300)  # Retry after 5 minutes


@shared_task(bind=True, max_retries=3)
def send_task_reminder(self):
    """
    Send reminders for tasks approaching deadline.
    
    Workflow:
    1. Find tasks with deadline in next 24 hours
    2. Send reminder to assigned tasker
    3. Send reminder to task owner
    
    Runs: Daily at 9 AM (configured in celery.py)
    """
    from .models import Task
    from apps.notifications.services import NotificationService
    
    try:
        # Find tasks with deadline in next 24 hours
        now = timezone.now()
        tomorrow = now + timedelta(hours=24)
        
        upcoming_tasks = Task.objects.filter(
            status='in_progress',
            deadline__gte=now,
            deadline__lte=tomorrow
        )
        
        reminder_count = 0
        
        for task in upcoming_tasks:
            try:
                # Send reminder to tasker
                if task.assigned_to:
                    NotificationService.send_notification(
                        user=task.assigned_to,
                        notification_type='task_reminder',
                        title='Task Deadline Approaching',
                        message=f'Reminder: Task "{task.title}" is due in less than 24 hours.',
                        related_object=task,
                        priority='high'
                    )
                
                # Send reminder to owner
                NotificationService.send_notification(
                    user=task.owner,
                    notification_type='task_reminder',
                    title='Task Deadline Approaching',
                    message=f'Reminder: Your task "{task.title}" deadline is approaching.',
                    related_object=task,
                    priority='normal'
                )
                
                reminder_count += 1
                logger.info(f"Sent reminder for task {task.id}: {task.title}")
                
            except Exception as e:
                logger.error(f"Error sending reminder for task {task.id}: {e}")
                continue
        
        logger.info(f"Sent {reminder_count} task reminders")
        return {
            'success': True,
            'reminder_count': reminder_count
        }
        
    except Exception as exc:
        logger.error(f"Error in send_task_reminder: {exc}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, max_retries=3)
def cleanup_expired_tasks(self):
    """
    Archive old completed/cancelled tasks.
    
    Workflow:
    1. Find tasks completed/cancelled > 90 days ago
    2. Mark as archived
    3. Clean up associated data
    
    Runs: Daily at 2 AM (configured in celery.py)
    """
    from .models import Task
    
    try:
        # Find tasks to archive (completed/cancelled > 90 days ago)
        cutoff_date = timezone.now() - timedelta(days=90)
        
        old_tasks = Task.objects.filter(
            Q(status='completed', completed_at__lt=cutoff_date) |
            Q(status='cancelled', updated_at__lt=cutoff_date)
        ).filter(is_archived=False)
        
        archived_count = old_tasks.update(is_archived=True)
        
        logger.info(f"Archived {archived_count} old tasks")
        return {
            'success': True,
            'archived_count': archived_count
        }
        
    except Exception as exc:
        logger.error(f"Error in cleanup_expired_tasks: {exc}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True)
def send_task_status_update(self, task_id: str, status: str):
    """
    Send task status update notifications.
    
    Args:
        task_id: Task ID
        status: New status
    """
    from .models import Task
    from apps.notifications.services import NotificationService
    
    try:
        task = Task.objects.get(id=task_id)
        
        # Notification messages based on status
        status_messages = {
            'open': 'Your task has been posted and is now open for bids.',
            'assigned': 'Your task has been assigned to a tasker.',
            'in_progress': 'Work has started on your task.',
            'completed': 'Your task has been completed.',
            'approved': 'Your task has been approved and payment released.',
            'cancelled': 'Your task has been cancelled.',
        }
        
        message = status_messages.get(status, f'Your task status has been updated to {status}.')
        
        # Send to task owner
        NotificationService.send_notification(
            user=task.owner,
            notification_type='task_status_update',
            title=f'Task {status.title()}',
            message=message,
            related_object=task,
            priority='normal'
        )
        
        # Send to assigned tasker if exists
        if task.assigned_to and status in ['assigned', 'in_progress', 'completed', 'approved']:
            NotificationService.send_notification(
                user=task.assigned_to,
                notification_type='task_status_update',
                title=f'Task {status.title()}',
                message=f'Task "{task.title}" status updated to {status}.',
                related_object=task,
                priority='normal'
            )
        
        logger.info(f"Sent status update notification for task {task_id}: {status}")
        return {'success': True}
        
    except Task.DoesNotExist:
        logger.error(f"Task {task_id} not found")
        return {'success': False, 'error': 'Task not found'}
    except Exception as e:
        logger.error(f"Error sending task status update: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(bind=True)
def process_task_completion(self, task_id: str):
    """
    Process task completion workflow.
    
    Workflow:
    1. Update task status
    2. Release escrow payment
    3. Send notifications
    4. Update user statistics
    
    Args:
        task_id: Task ID
    """
    from .models import Task
    from apps.payments.services import EscrowService
    from apps.notifications.services import NotificationService
    
    try:
        task = Task.objects.get(id=task_id)
        
        # Release escrow payment
        try:
            payment = EscrowService.release_escrow_on_completion(task)
            logger.info(f"Released escrow payment {payment.id} for task {task_id}")
        except Exception as e:
            logger.error(f"Error releasing escrow for task {task_id}: {e}")
        
        # Send completion notifications
        NotificationService.send_notification(
            user=task.owner,
            notification_type='task_completed',
            title='Task Completed',
            message=f'Task "{task.title}" has been completed successfully.',
            related_object=task,
            priority='normal'
        )
        
        if task.assigned_to:
            NotificationService.send_notification(
                user=task.assigned_to,
                notification_type='payment_received',
                title='Payment Released',
                message=f'Payment for task "{task.title}" has been released to your wallet.',
                related_object=task,
                priority='high'
            )
        
        logger.info(f"Processed completion for task {task_id}")
        return {'success': True}
        
    except Task.DoesNotExist:
        logger.error(f"Task {task_id} not found")
        return {'success': False, 'error': 'Task not found'}
    except Exception as e:
        logger.error(f"Error processing task completion: {e}")
        return {'success': False, 'error': str(e)}
