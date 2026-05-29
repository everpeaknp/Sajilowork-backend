from apps.rules.context import RuleContext
from apps.rules.handlers.base import BaseRuleHandler
from apps.rules.models import RuleCategory, RulePolicy
from apps.rules.result import RuleEvaluationResult


class PromotionRuleHandler(BaseRuleHandler):
    category = RuleCategory.PROMOTION

    def evaluate_policy(self, policy: RulePolicy, context: RuleContext) -> RuleEvaluationResult:
        result = RuleEvaluationResult(event=context.event, allowed=True)
        if context.event == 'task.published' and policy.slug == 'boosted_visibility':
            if context.extra.get('is_featured'):
                boost = (policy.parameters or {}).get('rank_boost', 10)
                result.metadata['search_rank_boost'] = boost
        return result
