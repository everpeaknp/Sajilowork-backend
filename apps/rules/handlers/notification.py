from apps.rules.context import RuleContext
from apps.rules.handlers.base import BaseRuleHandler
from apps.rules.models import RuleCategory, RulePolicy
from apps.rules.result import RuleEvaluationResult


class NotificationRuleHandler(BaseRuleHandler):
    category = RuleCategory.NOTIFICATION

    def evaluate_policy(self, policy: RulePolicy, context: RuleContext) -> RuleEvaluationResult:
        result = RuleEvaluationResult(event=context.event, allowed=True)
        if context.event != 'notify.dispatch':
            return result

        allowed_types = (policy.parameters or {}).get('enabled_types')
        if allowed_types:
            ntype = context.extra.get('notification_type')
            if ntype and ntype not in allowed_types:
                result.metadata['skip_notification'] = True

        return result
