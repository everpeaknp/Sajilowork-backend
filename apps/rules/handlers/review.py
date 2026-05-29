from apps.rules.context import RuleContext
from apps.rules.handlers.base import BaseRuleHandler
from apps.rules.models import RuleCategory, RulePolicy
from apps.rules.result import RuleEvaluationResult, RuleViolation


class ReviewRuleHandler(BaseRuleHandler):
    category = RuleCategory.REVIEW

    def evaluate_policy(self, policy: RulePolicy, context: RuleContext) -> RuleEvaluationResult:
        result = RuleEvaluationResult(event=context.event, allowed=True)
        if context.event != 'review.submitted':
            return result

        if policy.slug == 'only_after_release':
            if not context.extra.get('payment_released'):
                result.allowed = False
                result.violations.append(
                    RuleViolation(
                        policy_slug=policy.slug,
                        category=self.category,
                        code='REVIEW_TOO_EARLY',
                        message='Reviews are allowed only after payment is released.',
                        blocking=True,
                    )
                )

        if policy.slug == 'one_review_per_task':
            from apps.reviews.models import Review

            if context.task_id and context.actor_id:
                exists = Review.objects.filter(
                    task_id=context.task_id,
                    reviewer_id=context.actor_id,
                ).exists()
                if exists:
                    result.allowed = False
                    result.violations.append(
                        RuleViolation(
                            policy_slug=policy.slug,
                            category=self.category,
                            code='DUPLICATE_REVIEW',
                            message='You already reviewed this task.',
                            blocking=True,
                        )
                    )

        return result
