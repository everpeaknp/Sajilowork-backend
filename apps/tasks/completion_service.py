"""Dual confirmation before task completion and escrow release."""
from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Task


def both_parties_marked_complete(task: Task) -> bool:
    return bool(task.tasker_marked_complete_at and task.owner_marked_complete_at)


def is_legacy_completed_without_confirm_flags(task: Task) -> bool:
    """Tasks completed before dual-confirm fields were added."""
    return (
        task.status == 'completed'
        and not task.tasker_marked_complete_at
        and not task.owner_marked_complete_at
    )


def ready_for_payout(task: Task) -> bool:
    return both_parties_marked_complete(task) or is_legacy_completed_without_confirm_flags(
        task
    )


@transaction.atomic
def confirm_work_complete_by_user(task: Task, user) -> dict:
    """
    Record one party's completion confirmation. When both poster and tasker
    have confirmed, mark the task completed and release escrow to the tasker.
    """
    from apps.payments.escrow_lifecycle import EscrowLifecycleError, EscrowLifecycleService

    if task.status != 'in_progress':
        raise ValidationError('Work can only be confirmed while the task is in progress.')

    now = timezone.now()

    if task.owner_id == user.id:
        if task.owner_marked_complete_at:
            raise ValidationError('You have already confirmed that the work is complete.')
        task.owner_marked_complete_at = now
        task.save(update_fields=['owner_marked_complete_at', 'updated_at'])
    elif task.assigned_tasker_id == user.id:
        if task.tasker_marked_complete_at:
            raise ValidationError('You have already confirmed that the work is complete.')
        task.tasker_marked_complete_at = now
        if not task.completion_requested_at:
            task.completion_requested_at = now
        task.save(
            update_fields=[
                'tasker_marked_complete_at',
                'completion_requested_at',
                'updated_at',
            ]
        )
    else:
        raise PermissionDenied('You are not allowed to confirm completion for this task.')

    payment_released = None
    both_confirmed = both_parties_marked_complete(task)

    if both_confirmed:
        task.status = 'completed'
        task.completion_date = now
        task.completed_at = now
        task.save(
            update_fields=['status', 'completion_date', 'completed_at', 'updated_at']
        )
        try:
            payment_released = EscrowLifecycleService.release_escrow_for_completed_task(
                task, actor=user
            )
        except (EscrowLifecycleError, ValidationError) as exc:
            raise ValidationError(str(exc)) from exc

    return {
        'both_confirmed': both_confirmed,
        'tasker_marked_complete_at': task.tasker_marked_complete_at,
        'owner_marked_complete_at': task.owner_marked_complete_at,
        'payment_released': payment_released,
    }
