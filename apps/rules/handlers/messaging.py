import re

from apps.rules.context import RuleContext
from apps.rules.handlers.base import BaseRuleHandler
from apps.rules.models import RuleCategory, RulePolicy
from apps.rules.result import RuleEvaluationResult, RuleViolation


class MessagingRuleHandler(BaseRuleHandler):
    category = RuleCategory.MESSAGING

    PHONE_PATTERN = re.compile(
        r'(\+977|0)?[9][6-9]\d{8}|'
        r'\b\d{10}\b|'
        r'whatsapp|viber|call\s+me',
        re.IGNORECASE,
    )

    def evaluate_policy(self, policy: RulePolicy, context: RuleContext) -> RuleEvaluationResult:
        result = RuleEvaluationResult(event=context.event, allowed=True)
        if context.event != 'message.sent':
            return result

        body = (context.extra.get('message_body') or '')
        params = policy.parameters or {}

        if policy.slug == 'block_contact_before_assignment':
            if not context.extra.get('task_assigned') and params.get('enabled', True):
                if self.PHONE_PATTERN.search(body):
                    result.allowed = False
                    result.violations.append(
                        RuleViolation(
                            policy_slug=policy.slug,
                            category=self.category,
                            code='CONTACT_SHARING',
                            message='Sharing contact details before assignment is not allowed.',
                            blocking=params.get('blocking', True),
                        )
                    )

        return result
