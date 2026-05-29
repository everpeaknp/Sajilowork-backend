from django.db import transaction
from django.utils import timezone

from apps.notifications.services import NotificationService
from apps.rules.context import RuleContext
from apps.rules.engine import RuleEngine
from apps.rules.events import RuleEvent
from apps.tasks.models import Task

from .models import Dispute


class DisputeService:
    @staticmethod
    @transaction.atomic
    def open_dispute(*, task: Task, raised_by, against, dispute_type: str, title: str, description: str) -> Dispute:
        if task.status in ('cancelled', 'completed'):
            from rest_framework.exceptions import ValidationError

            raise ValidationError('Cannot dispute this task in its current state.')

        dispute = Dispute.objects.create(
            task=task,
            raised_by=raised_by,
            against=against,
            dispute_type=dispute_type,
            title=title,
            description=description,
            status='open',
        )

        task.status = 'disputed'
        task.save(update_fields=['status', 'updated_at'])

        ctx = RuleContext(
            event=RuleEvent.TASK_DISPUTED,
            actor_id=str(raised_by.pk),
            task_id=str(task.pk),
            dispute_id=str(dispute.pk),
            task_status=task.status,
        )
        result = RuleEngine.evaluate(ctx, audit=True)
        RuleEngine.apply_actions(result)

        for user in {task.owner, task.assigned_tasker} - {None}:
            if user and user != raised_by:
                NotificationService.send_notification(
                    user=user,
                    notification_type='task_updated',
                    title='Dispute opened',
                    message=f'A dispute was opened for task "{task.title}".',
                    related_object=dispute,
                    data={'task_id': str(task.id), 'dispute_id': str(dispute.id)},
                )

        return dispute

    @staticmethod
    @transaction.atomic
    def resolve_dispute(*, dispute: Dispute, admin_user, resolution: str, notes: str = '') -> Dispute:
        dispute.status = 'resolved'
        dispute.resolution = resolution
        dispute.resolution_notes = notes
        dispute.resolved_by = admin_user
        dispute.resolved_at = timezone.now()
        dispute.save()

        return dispute
