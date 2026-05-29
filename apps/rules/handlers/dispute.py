from apps.rules.context import RuleContext
from apps.rules.handlers.base import BaseRuleHandler
from apps.rules.models import RuleCategory, RulePolicy
from apps.rules.result import RuleAction, RuleEvaluationResult


class DisputeRuleHandler(BaseRuleHandler):
    category = RuleCategory.DISPUTE

    def evaluate_policy(self, policy: RulePolicy, context: RuleContext) -> RuleEvaluationResult:
        result = RuleEvaluationResult(event=context.event, allowed=True)
        if context.event != 'task.disputed':
            return result

        if policy.slug == 'freeze_escrow_on_dispute':
            result.actions.append(
                RuleAction(action_type='FREEZE_ESCROW', payload={'task_id': context.task_id})
            )

        return result
