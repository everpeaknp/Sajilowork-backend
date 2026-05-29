from apps.rules.context import RuleContext
from apps.rules.handlers.base import BaseRuleHandler
from apps.rules.models import RuleCategory, RulePolicy
from apps.rules.result import RuleAction, RuleEvaluationResult


class RefundRuleHandler(BaseRuleHandler):
    category = RuleCategory.REFUND

    def evaluate_policy(self, policy: RulePolicy, context: RuleContext) -> RuleEvaluationResult:
        result = RuleEvaluationResult(event=context.event, allowed=True)

        if context.event == 'refund.issued' and policy.slug == 'notify_on_refund':
            result.actions.append(
                RuleAction(
                    action_type='NOTIFY',
                    payload={
                        'type': 'payment_refunded',
                        'task_id': context.task_id,
                    },
                )
            )

        return result
