from django.contrib.auth import get_user_model

from apps.bids.models import Bid
from apps.rules.context import RuleContext
from apps.rules.handlers.base import BaseRuleHandler
from apps.rules.models import RuleCategory, RulePolicy
from apps.rules.result import RuleEvaluationResult, RuleViolation

User = get_user_model()


class OfferRuleHandler(BaseRuleHandler):
    category = RuleCategory.OFFER

    def evaluate_policy(self, policy: RulePolicy, context: RuleContext) -> RuleEvaluationResult:
        result = RuleEvaluationResult(event=context.event, allowed=True)
        params = policy.parameters or {}

        if context.event != 'bid.created' or not context.task_id or not context.actor_id:
            return result

        from apps.tasks.models import Task

        try:
            task = Task.objects.get(pk=context.task_id)
        except Task.DoesNotExist:
            return result

        if policy.slug == 'no_self_bid' and str(task.owner_id) == str(context.actor_id):
            result.allowed = False
            result.violations.append(
                RuleViolation(
                    policy_slug=policy.slug,
                    category=self.category,
                    code='SELF_BID',
                    message='You cannot bid on your own task.',
                    blocking=True,
                )
            )

        if policy.slug == 'no_duplicate_bid':
            if Bid.objects.filter(task_id=task.id, bidder_id=context.actor_id).exclude(
                status='withdrawn'
            ).exists():
                result.allowed = False
                result.violations.append(
                    RuleViolation(
                        policy_slug=policy.slug,
                        category=self.category,
                        code='DUPLICATE_BID',
                        message='You already submitted an offer on this task.',
                        blocking=True,
                    )
                )

        max_per_day = params.get('max_bids_per_day')
        if max_per_day and policy.slug == 'bid_daily_limit':
            from django.utils import timezone

            today = timezone.now().date()
            count = Bid.objects.filter(
                bidder_id=context.actor_id,
                created_at__date=today,
            ).count()
            if count >= int(max_per_day):
                result.allowed = False
                result.violations.append(
                    RuleViolation(
                        policy_slug=policy.slug,
                        category=self.category,
                        code='BID_LIMIT',
                        message=f'Daily offer limit reached ({max_per_day}).',
                        blocking=True,
                    )
                )

        return result
