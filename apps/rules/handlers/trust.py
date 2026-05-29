from apps.rules.context import RuleContext
from apps.rules.handlers.base import BaseRuleHandler
from apps.rules.models import RuleCategory, RulePolicy
from apps.rules.result import RuleEvaluationResult


class TrustRuleHandler(BaseRuleHandler):
    category = RuleCategory.TRUST

    def evaluate_policy(self, policy: RulePolicy, context: RuleContext) -> RuleEvaluationResult:
        result = RuleEvaluationResult(event=context.event, allowed=True)
        params = policy.parameters or {}

        if policy.slug == 'min_trust_for_visibility':
            score = context.extra.get('trust_score')
            minimum = params.get('minimum_score')
            if score is not None and minimum is not None and float(score) < float(minimum):
                result.metadata['reduce_visibility'] = True

        return result
