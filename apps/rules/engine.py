"""Central marketplace rule engine."""

from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.rules.context import RuleContext
from apps.rules.models import RuleEvaluationLog, RulePolicy
from apps.rules.registry import categories_for_event, get_handler
from apps.rules.result import RuleAction, RuleEvaluationResult, RuleViolation

logger = logging.getLogger(__name__)
User = get_user_model()


class RuleEngine:
    """
    Event-driven policy evaluator.
    Loads active RulePolicy rows, dispatches to category handlers, audits results.
    """

    @staticmethod
    def _policies_for_event(event: str) -> dict[str, list[RulePolicy]]:
        categories = categories_for_event(event)
        if not categories:
            return {}

        qs = RulePolicy.objects.filter(is_active=True, category__in=categories).order_by(
            '-priority', 'slug'
        )
        grouped: dict[str, list[RulePolicy]] = {c: [] for c in categories}
        for policy in qs:
            triggers = policy.event_triggers or []
            if triggers and event not in triggers:
                continue
            grouped.setdefault(policy.category, []).append(policy)
        return grouped

    @staticmethod
    def evaluate(
        context: RuleContext,
        *,
        audit: bool = True,
        stop_on_block: bool = True,
    ) -> RuleEvaluationResult:
        grouped = RuleEngine._policies_for_event(context.event)
        aggregate = RuleEvaluationResult(event=context.event, allowed=True)

        for category, policies in grouped.items():
            if not policies:
                continue
            handler = get_handler(category)
            if not handler:
                continue
            partial = handler.evaluate(policies, context)
            aggregate.merge(partial)
            if stop_on_block and not partial.allowed:
                break

        if audit:
            RuleEngine._write_audit(context, aggregate)
        return aggregate

    @staticmethod
    def evaluate_or_raise(context: RuleContext) -> RuleEvaluationResult:
        result = RuleEngine.evaluate(context)
        if not result.allowed:
            msg = result.blocking_message or 'Action blocked by platform policy.'
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(msg)
        return result

    @staticmethod
    def _write_audit(context: RuleContext, result: RuleEvaluationResult) -> None:
        try:
            actor = None
            if context.actor_id:
                actor = User.objects.filter(pk=context.actor_id).first()
            task = None
            if context.task_id:
                from apps.tasks.models import Task

                task = Task.objects.filter(pk=context.task_id).first()

            RuleEvaluationLog.objects.create(
                event=context.event,
                actor=actor,
                task=task,
                allowed=result.allowed,
                policies_evaluated=result.policies_evaluated,
                violations=[
                    {
                        'slug': v.policy_slug,
                        'category': v.category,
                        'code': v.code,
                        'message': v.message,
                        'blocking': v.blocking,
                    }
                    for v in result.violations
                ],
                actions=[{'type': a.action_type, 'payload': a.payload} for a in result.actions],
                context_snapshot=context.to_dict(),
            )
        except Exception:
            logger.exception('Failed to write rule evaluation audit log')

    @staticmethod
    @transaction.atomic
    def apply_actions(result: RuleEvaluationResult) -> None:
        """Execute automatic actions returned by handlers (idempotent where possible)."""
        for action in result.actions:
            RuleEngine._apply_action(action)

    @staticmethod
    def _apply_action(action: RuleAction) -> None:
        if action.action_type == 'REFUND_ESCROW':
            task_id = action.payload.get('task_id')
            reason = action.payload.get('reason', '')
            if not task_id:
                return
            from apps.tasks.models import Task
            from apps.payments.services import EscrowService

            task = Task.objects.filter(pk=task_id).first()
            if task and task.status == 'cancelled':
                try:
                    EscrowService.refund_escrow_on_cancellation(task, reason)
                except Exception:
                    logger.exception('Rule engine escrow refund failed for task %s', task_id)

        elif action.action_type == 'MODERATION_CHECK':
            user_id = action.payload.get('user_id')
            if user_id:
                from apps.rules.services import ModerationService

                user = User.objects.filter(pk=user_id).first()
                if user:
                    ModerationService.on_task_cancelled(user)

        elif action.action_type == 'FREEZE_ESCROW':
            task_id = action.payload.get('task_id')
            if task_id:
                from apps.payments.models import Escrow

                Escrow.objects.filter(task_id=task_id).exclude(
                    status__in=['released', 'refunded', 'cancelled']
                ).update(status='disputed')
