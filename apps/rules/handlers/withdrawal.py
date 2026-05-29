from decimal import Decimal

from apps.rules.context import RuleContext
from apps.rules.handlers.base import BaseRuleHandler
from apps.rules.models import RuleCategory, RulePolicy
from apps.rules.result import RuleEvaluationResult, RuleViolation


class WithdrawalRuleHandler(BaseRuleHandler):
    category = RuleCategory.WITHDRAWAL

    def evaluate_policy(self, policy: RulePolicy, context: RuleContext) -> RuleEvaluationResult:
        result = RuleEvaluationResult(event=context.event, allowed=True)
        if context.event != 'withdrawal.requested':
            return result

        params = policy.parameters or {}
        amount = Decimal(str(context.extra.get('amount', '0')))

        if policy.slug == 'withdrawal_amount_limits':
            min_amt = params.get('min_withdrawal_amount_npr')
            max_amt = params.get('max_withdrawal_amount_npr')
            if min_amt is not None and amount < Decimal(str(min_amt)):
                result.allowed = False
                result.violations.append(
                    RuleViolation(
                        policy_slug=policy.slug,
                        category=self.category,
                        code='MIN_AMOUNT',
                        message=f'Minimum withdrawal amount is NPR {min_amt}.',
                        blocking=True,
                    )
                )
            if max_amt is not None and amount > Decimal(str(max_amt)):
                result.allowed = False
                result.violations.append(
                    RuleViolation(
                        policy_slug=policy.slug,
                        category=self.category,
                        code='MAX_AMOUNT',
                        message=f'Maximum withdrawal amount is NPR {max_amt}.',
                        blocking=True,
                    )
                )

        daily_limit = params.get('daily_limit_npr')
        if policy.slug == 'daily_withdrawal_limit' and daily_limit:
            daily_total = Decimal(str(context.extra.get('daily_withdrawn', '0')))
            if daily_total + amount > Decimal(str(daily_limit)):
                result.allowed = False
                result.violations.append(
                    RuleViolation(
                        policy_slug=policy.slug,
                        category=self.category,
                        code='DAILY_LIMIT',
                        message=f'Daily withdrawal limit of NPR {daily_limit} exceeded.',
                        blocking=True,
                    )
                )

        admin_threshold = params.get('admin_approval_above_npr')
        if policy.slug == 'admin_approval_large_withdrawals' and admin_threshold:
            if amount >= Decimal(str(admin_threshold)):
                result.metadata['requires_admin_approval'] = True

        cooldown_hours = params.get('cooldown_hours')
        if policy.slug == 'withdrawal_cooldown' and cooldown_hours:
            if context.extra.get('within_cooldown'):
                result.allowed = False
                result.violations.append(
                    RuleViolation(
                        policy_slug=policy.slug,
                        category=self.category,
                        code='COOLDOWN',
                        message=f'Please wait {cooldown_hours} hours between withdrawals.',
                        blocking=True,
                    )
                )

        return result
