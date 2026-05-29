from apps.rules.context import RuleContext
from apps.rules.handlers.base import BaseRuleHandler
from apps.rules.models import RuleCategory, RulePolicy
from apps.rules.result import RuleEvaluationResult, RuleViolation


class FraudRuleHandler(BaseRuleHandler):
    category = RuleCategory.FRAUD

    def evaluate_policy(self, policy: RulePolicy, context: RuleContext) -> RuleEvaluationResult:
        result = RuleEvaluationResult(event=context.event, allowed=True)
        params = policy.parameters or {}

        if policy.slug == 'velocity_check':
            count = context.extra.get('action_count_1h', 0)
            limit = params.get('max_actions_per_hour', 50)
            if count >= limit:
                result.allowed = False
                result.violations.append(
                    RuleViolation(
                        policy_slug=policy.slug,
                        category=self.category,
                        code='VELOCITY_LIMIT',
                        message='Too many actions in a short period. Please try again later.',
                        blocking=True,
                    )
                )

        return result
