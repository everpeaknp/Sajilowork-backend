from apps.rules.context import RuleContext
from apps.rules.handlers.base import BaseRuleHandler
from apps.rules.models import RuleCategory, RulePolicy
from apps.rules.result import RuleEvaluationResult


class TaskExpiryRuleHandler(BaseRuleHandler):
    category = RuleCategory.TASK_EXPIRY

    def evaluate_policy(self, policy: RulePolicy, context: RuleContext) -> RuleEvaluationResult:
        result = RuleEvaluationResult(event=context.event, allowed=True)
        params = policy.parameters or {}

        if policy.slug == 'expire_unassigned_open_tasks':
            result.metadata['expire_open_after_days'] = params.get('days', 30)

        if policy.slug == 'expire_unfunded_assigned':
            result.metadata['expire_assigned_without_payment_days'] = params.get('days', 7)

        return result
