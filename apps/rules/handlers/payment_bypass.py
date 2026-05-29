import re

from apps.rules.context import RuleContext
from apps.rules.handlers.base import BaseRuleHandler
from apps.rules.models import RuleCategory, RulePolicy
from apps.rules.result import RuleEvaluationResult, RuleViolation


class PaymentBypassRuleHandler(BaseRuleHandler):
    category = RuleCategory.PAYMENT_BYPASS

    BYPASS_PATTERN = re.compile(
        r'esewa|khalti|bank\s+transfer|pay\s+outside|cash\s+payment|'
        r'offline\s+payment|direct\s+payment|bypass\s+platform',
        re.IGNORECASE,
    )

    def evaluate_policy(self, policy: RulePolicy, context: RuleContext) -> RuleEvaluationResult:
        result = RuleEvaluationResult(event=context.event, allowed=True)
        if context.event not in ('message.sent', 'payment_bypass.detected'):
            return result

        text = context.extra.get('message_body') or context.extra.get('text') or ''
        if policy.slug == 'detect_external_payment' and self.BYPASS_PATTERN.search(text):
            result.allowed = False
            result.violations.append(
                RuleViolation(
                    policy_slug=policy.slug,
                    category=self.category,
                    code='PAYMENT_BYPASS',
                    message='Off-platform payments are not allowed. Use platform escrow.',
                    blocking=True,
                )
            )

        return result
