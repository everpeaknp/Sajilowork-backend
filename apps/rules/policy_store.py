from __future__ import annotations

from typing import Any

from .models import RulePolicy


def get_active_policy_parameters(category: str, slug: str) -> dict[str, Any]:
    """
    Fetch parameters for the highest-priority active policy.

    Used as a lightweight "admin-configured settings" store for limits that need
    to be enforced outside the event-driven rule engine.
    """

    policy = (
        RulePolicy.objects.filter(category=category, slug=slug, is_active=True)
        .order_by("-priority")
        .first()
    )
    return dict(policy.parameters or {}) if policy else {}

