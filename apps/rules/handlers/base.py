"""Base class for category rule handlers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from apps.rules.context import RuleContext
from apps.rules.models import RulePolicy
from apps.rules.result import RuleEvaluationResult


class BaseRuleHandler(ABC):
    category: str = ''

    @abstractmethod
    def evaluate_policy(self, policy: RulePolicy, context: RuleContext) -> RuleEvaluationResult:
        """Evaluate a single policy against context."""

    def matches_conditions(self, policy: RulePolicy, context: RuleContext) -> bool:
        conditions = policy.conditions or {}
        if not conditions:
            return True

        roles = conditions.get('roles')
        if roles and context.user_role and context.user_role not in roles:
            return False

        statuses = conditions.get('task_statuses')
        if statuses and context.task_status and context.task_status not in statuses:
            return False

        events = policy.event_triggers or []
        if events and context.event not in events:
            return False

        return True

    def evaluate(self, policies: list[RulePolicy], context: RuleContext) -> RuleEvaluationResult:
        result = RuleEvaluationResult(event=context.event)
        for policy in policies:
            if not self.matches_conditions(policy, context):
                continue
            partial = self.evaluate_policy(policy, context)
            partial.policies_evaluated = 1
            result.merge(partial)
            if not partial.allowed and policy.enforcement == 'BLOCK':
                break
        return result
