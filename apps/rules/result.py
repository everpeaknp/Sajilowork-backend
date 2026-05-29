"""Rule engine evaluation results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuleViolation:
    policy_slug: str
    category: str
    code: str
    message: str
    blocking: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleAction:
    """Side effect the engine or caller should apply."""

    action_type: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleEvaluationResult:
    event: str
    allowed: bool = True
    violations: list[RuleViolation] = field(default_factory=list)
    actions: list[RuleAction] = field(default_factory=list)
    policies_evaluated: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def merge(self, other: RuleEvaluationResult) -> None:
        self.policies_evaluated += other.policies_evaluated
        self.violations.extend(other.violations)
        self.actions.extend(other.actions)
        self.metadata.update(other.metadata)
        if not other.allowed:
            self.allowed = False

    @property
    def blocking_message(self) -> str | None:
        for v in self.violations:
            if v.blocking:
                return v.message
        return None
