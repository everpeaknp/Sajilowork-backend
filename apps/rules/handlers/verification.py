from apps.rules.context import RuleContext
from apps.rules.handlers.base import BaseRuleHandler
from apps.rules.models import RuleCategory, RulePolicy
from apps.rules.result import RuleEvaluationResult, RuleViolation


class VerificationRuleHandler(BaseRuleHandler):
    category = RuleCategory.VERIFICATION

    def evaluate_policy(self, policy: RulePolicy, context: RuleContext) -> RuleEvaluationResult:
        result = RuleEvaluationResult(event=context.event, allowed=True)
        params = policy.parameters or {}

        if policy.slug == 'kyc_for_withdrawal' and context.event == 'withdrawal.requested':
            if params.get('require_id_verified') and not context.extra.get('id_verified'):
                result.allowed = False
                result.violations.append(
                    RuleViolation(
                        policy_slug=policy.slug,
                        category=self.category,
                        code='KYC_REQUIRED',
                        message='Identity verification is required before withdrawal.',
                        blocking=True,
                    )
                )

        return result
