from apps.rules.context import RuleContext
from apps.rules.handlers.base import BaseRuleHandler
from apps.rules.models import RuleCategory, RulePolicy
from apps.rules.result import RuleEvaluationResult


class AutoReleaseRuleHandler(BaseRuleHandler):
    category = RuleCategory.AUTO_RELEASE

    def evaluate_policy(self, policy: RulePolicy, context: RuleContext) -> RuleEvaluationResult:
        result = RuleEvaluationResult(event=context.event, allowed=True)
        params = policy.parameters or {}

        if policy.slug == 'auto_release_after_inactivity':
            hours = params.get('hours', 48)
            result.metadata['auto_release_hours'] = hours
            result.metadata['send_reminder_hours_before'] = params.get('reminder_hours_before', 24)

        return result
