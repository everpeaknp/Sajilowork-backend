"""High-level integration hooks for domain services and views."""

from __future__ import annotations

from django.db import transaction

from apps.rules.context import RuleContext
from apps.rules.engine import RuleEngine
from apps.rules.events import RuleEvent
from apps.rules.result import RuleEvaluationResult


def build_context(
    event: str,
    *,
    actor=None,
    task=None,
    **extra,
) -> RuleContext:
    return RuleContext(
        event=event,
        actor_id=str(actor.pk) if actor else None,
        task_id=str(task.pk) if task else None,
        task_status=getattr(task, 'status', None),
        task_amount=getattr(task, 'budget_amount', None),
        user_role=getattr(actor, 'role', None) if actor else None,
        cancellation_reason=extra.pop('cancellation_reason', ''),
        extra=extra,
    )


def dispatch_event(event: str, context: RuleContext, *, apply_actions: bool = False) -> RuleEvaluationResult:
    result = RuleEngine.evaluate(context)
    if apply_actions and result.allowed:
        RuleEngine.apply_actions(result)
    return result


@transaction.atomic
def cancel_task_with_rules(task, user, reason: str = '') -> dict:
    """
    Production cancellation path: evaluate rules → refund escrow → cancel task → moderation.
  """
    from rest_framework.exceptions import PermissionDenied

    from apps.rules.services import ModerationService

    if ModerationService.is_user_suspended(user):
        raise PermissionDenied(
            'Your account is temporarily suspended due to repeated task cancellations.'
        )

    ctx = build_context(
        RuleEvent.TASK_CANCELLED,
        actor=user,
        task=task,
        cancellation_reason=reason,
    )

    pre = RuleEngine.evaluate(ctx, audit=True)
    if not pre.allowed:
        raise PermissionDenied(pre.blocking_message or 'Cancellation blocked by platform policy.')

    if task.status in ('assigned', 'funded', 'in_progress', 'pending_approval'):
        from apps.payments.services import EscrowService

        try:
            EscrowService.refund_escrow_on_cancellation(task, reason)
        except Exception:
            pass

    task.cancel(user=user, cancellation_reason=reason)

    post_ctx = build_context(RuleEvent.TASK_CANCELLED, actor=user, task=task, cancellation_reason=reason)
    post = RuleEngine.evaluate(post_ctx, audit=True)
    RuleEngine.apply_actions(post)

    suspension = ModerationService.on_task_cancelled(user)
    payload = {'message': 'Task cancelled successfully.'}
    if suspension:
        payload['account_suspended'] = True
        payload['suspended_until'] = suspension['suspended_until'].isoformat()
        payload['suspension_reason'] = suspension['reason']
    return payload


def validate_bid_created(*, task, bidder) -> RuleEvaluationResult:
    ctx = build_context(
        RuleEvent.BID_CREATED,
        actor=bidder,
        task=task,
        bid_id=None,
    )
    return RuleEngine.evaluate(ctx)


def validate_withdrawal(*, user, amount, extra: dict | None = None) -> RuleEvaluationResult:
    ctx = RuleContext(
        event=RuleEvent.WITHDRAWAL_REQUESTED,
        actor_id=str(user.pk),
        user_role=user.role,
        extra=extra or {},
    )
    ctx.extra['amount'] = str(amount)
    return RuleEngine.evaluate(ctx)
