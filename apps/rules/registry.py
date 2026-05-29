"""Handler registry — maps RuleCategory to handler instances."""

from __future__ import annotations

from apps.rules.handlers import ALL_HANDLERS
from apps.rules.handlers.base import BaseRuleHandler
from apps.rules.models import RuleCategory

_HANDLERS: dict[str, BaseRuleHandler] = {h.category: h for h in ALL_HANDLERS}

# Events that trigger evaluation for each category (when policy.event_triggers is empty)
EVENT_CATEGORY_MAP: dict[str, list[str]] = {
    'task.funded': [RuleCategory.ESCROW],
    'task.started': [RuleCategory.ESCROW, RuleCategory.ASSIGNMENT],
    'task.cancelled': [RuleCategory.CANCELLATION, RuleCategory.MODERATION, RuleCategory.REFUND],
    'task.disputed': [RuleCategory.DISPUTE, RuleCategory.ESCROW],
    'task.completed': [RuleCategory.REVIEW],
    'task.expired': [RuleCategory.TASK_EXPIRY],
    'task.published': [RuleCategory.PROMOTION, RuleCategory.TASK_EXPIRY],
    'bid.created': [RuleCategory.OFFER, RuleCategory.FRAUD],
    'bid.accepted': [RuleCategory.ASSIGNMENT, RuleCategory.ESCROW],
    'escrow.auto_release': [RuleCategory.AUTO_RELEASE],
    'review.submitted': [RuleCategory.REVIEW],
    'withdrawal.requested': [RuleCategory.WITHDRAWAL, RuleCategory.WALLET, RuleCategory.VERIFICATION],
    'message.sent': [RuleCategory.MESSAGING, RuleCategory.PAYMENT_BYPASS],
    'payment_bypass.detected': [RuleCategory.PAYMENT_BYPASS],
    'refund.issued': [RuleCategory.REFUND],
    'notify.dispatch': [RuleCategory.NOTIFICATION],
    'fraud.signal': [RuleCategory.FRAUD],
    'trust.updated': [RuleCategory.TRUST],
    'user.verified': [RuleCategory.VERIFICATION, RuleCategory.TRUST],
}


def get_handler(category: str) -> BaseRuleHandler | None:
    return _HANDLERS.get(category)


def categories_for_event(event: str) -> list[str]:
    return EVENT_CATEGORY_MAP.get(event, [])
