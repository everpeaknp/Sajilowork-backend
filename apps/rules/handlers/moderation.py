from apps.rules.context import RuleContext
from apps.rules.handlers.base import BaseRuleHandler
from apps.rules.models import RuleCategory, RulePolicy
from apps.rules.result import RuleEvaluationResult, RuleViolation
from apps.rules.services import ModerationService


class ModerationRuleHandler(BaseRuleHandler):
    category = RuleCategory.MODERATION

    def evaluate_policy(self, policy: RulePolicy, context: RuleContext) -> RuleEvaluationResult:
        result = RuleEvaluationResult(event=context.event, allowed=True)
        if context.event != 'task.cancelled' or not context.actor_id:
            return result

        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            user = User.objects.get(pk=context.actor_id)
        except User.DoesNotExist:
            return result

        if ModerationService.is_user_suspended(user):
            result.allowed = False
            result.violations.append(
                RuleViolation(
                    policy_slug=policy.slug,
                    category=self.category,
                    code='ACCOUNT_SUSPENDED',
                    message='Your account is temporarily suspended.',
                    blocking=True,
                )
            )
        return result
