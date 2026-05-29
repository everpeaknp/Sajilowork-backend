from apps.rules.context import RuleContext
from apps.rules.handlers.base import BaseRuleHandler
from apps.rules.models import RuleCategory, RulePolicy
from apps.rules.result import RuleEvaluationResult, RuleViolation


class EscrowRuleHandler(BaseRuleHandler):
    category = RuleCategory.ESCROW

    def evaluate_policy(self, policy: RulePolicy, context: RuleContext) -> RuleEvaluationResult:
        result = RuleEvaluationResult(event=context.event, allowed=True)
        params = policy.parameters or {}

        if policy.slug == 'require_payment_before_start':
            if context.event == 'task.started' and context.task_status in ('open', 'assigned'):
                result.allowed = False
                result.violations.append(
                    RuleViolation(
                        policy_slug=policy.slug,
                        category=self.category,
                        code='ESCROW_NOT_FUNDED',
                        message=params.get(
                            'message',
                            'Customer must fund escrow before work can start.',
                        ),
                        blocking=True,
                    )
                )

        if policy.slug == 'freeze_on_dispute' and context.event == 'task.disputed':
            result.metadata['freeze_escrow'] = True

        return result
