from decimal import Decimal

from apps.rules.context import RuleContext
from apps.rules.handlers.base import BaseRuleHandler
from apps.rules.models import RuleCategory, RulePolicy
from apps.rules.result import RuleEvaluationResult, RuleViolation


class WalletRuleHandler(BaseRuleHandler):
    category = RuleCategory.WALLET

    def evaluate_policy(self, policy: RulePolicy, context: RuleContext) -> RuleEvaluationResult:
        result = RuleEvaluationResult(event=context.event, allowed=True)
        params = policy.parameters or {}

        if policy.slug == 'no_negative_balance':
            amount = context.extra.get('debit_amount')
            if amount is not None:
                available = Decimal(str(context.extra.get('available_balance', '0')))
                if available < Decimal(str(amount)):
                    result.allowed = False
                    result.violations.append(
                        RuleViolation(
                            policy_slug=policy.slug,
                            category=self.category,
                            code='INSUFFICIENT_BALANCE',
                            message='Insufficient available wallet balance.',
                            blocking=True,
                        )
                    )

        if policy.slug == 'locked_cannot_withdraw' and context.event == 'withdrawal.requested':
            held = Decimal(str(context.extra.get('held_balance', '0')))
            if held > 0 and params.get('block_if_locked', True):
                result.allowed = False
                result.violations.append(
                    RuleViolation(
                        policy_slug=policy.slug,
                        category=self.category,
                        code='FUNDS_LOCKED',
                        message='Locked escrow funds cannot be withdrawn.',
                        blocking=True,
                    )
                )

        return result
