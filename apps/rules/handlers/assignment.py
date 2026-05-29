from apps.rules.context import RuleContext
from apps.rules.handlers.base import BaseRuleHandler
from apps.rules.models import RuleCategory, RulePolicy
from apps.rules.result import RuleAction, RuleEvaluationResult


class AssignmentRuleHandler(BaseRuleHandler):
    category = RuleCategory.ASSIGNMENT

    def evaluate_policy(self, policy: RulePolicy, context: RuleContext) -> RuleEvaluationResult:
        result = RuleEvaluationResult(event=context.event, allowed=True)
        if context.event != 'bid.accepted':
            return result

        if policy.slug == 'lock_task_on_accept':
            result.actions.append(
                RuleAction(action_type='REJECT_OTHER_BIDS', payload={'task_id': context.task_id})
            )
            result.metadata['require_escrow_funding'] = policy.parameters.get('require_escrow_funding', True)

        return result
