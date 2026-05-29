from apps.rules.context import RuleContext
from apps.rules.handlers.base import BaseRuleHandler
from apps.rules.models import RuleCategory, RulePolicy
from apps.rules.result import RuleAction, RuleEvaluationResult


class CancellationRuleHandler(BaseRuleHandler):
    category = RuleCategory.CANCELLATION

    def evaluate_policy(self, policy: RulePolicy, context: RuleContext) -> RuleEvaluationResult:
        result = RuleEvaluationResult(event=context.event, allowed=True)
        if context.event != 'task.cancelled':
            return result

        params = policy.parameters or {}
        status = context.task_status or ''

        if policy.slug == 'free_cancel_before_assignment':
            if status in ('open', 'draft'):
                result.metadata['cancellation_fee_stage'] = 'BEFORE_ACCEPT'
                result.metadata['fee_waived'] = True

        if policy.slug == 'fee_after_assignment':
            if status in ('assigned', 'funded'):
                result.metadata['cancellation_fee_stage'] = 'AFTER_ACCEPT'

        if policy.slug == 'partial_compensation_in_progress':
            if status in ('in_progress', 'pending_approval'):
                result.metadata['cancellation_fee_stage'] = 'IN_PROGRESS'
                result.metadata['partial_tasker_compensation'] = params.get(
                    'compensation_percent', 0
                )

        if policy.slug == 'process_escrow_refund':
            result.actions.append(
                RuleAction(
                    action_type='REFUND_ESCROW',
                    payload={'task_id': context.task_id, 'reason': context.cancellation_reason},
                )
            )

        if policy.slug == 'apply_moderation_after_cancel':
            result.actions.append(
                RuleAction(action_type='MODERATION_CHECK', payload={'user_id': context.actor_id})
            )

        return result
