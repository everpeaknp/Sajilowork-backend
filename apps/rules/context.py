"""Rule evaluation context passed to all handlers."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass
class RuleContext:
    """Immutable-ish context for a single rule evaluation."""

    event: str
    actor_id: str | None = None
    task_id: str | None = None
    bid_id: str | None = None
    escrow_id: str | None = None
    payment_id: str | None = None
    wallet_id: str | None = None
    dispute_id: str | None = None
    review_id: str | None = None
    message_id: str | None = None
    withdrawal_id: str | None = None

    # Snapshots (avoid N+1 in handlers when already loaded)
    task_status: str | None = None
    task_amount: Decimal | None = None
    user_role: str | None = None
    cancellation_reason: str = ''
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'event': self.event,
            'actor_id': self.actor_id,
            'task_id': self.task_id,
            'bid_id': self.bid_id,
            'escrow_id': self.escrow_id,
            'payment_id': self.payment_id,
            'wallet_id': self.wallet_id,
            'dispute_id': self.dispute_id,
            'review_id': self.review_id,
            'message_id': self.message_id,
            'withdrawal_id': self.withdrawal_id,
            'task_status': self.task_status,
            'task_amount': str(self.task_amount) if self.task_amount is not None else None,
            'user_role': self.user_role,
            'cancellation_reason': self.cancellation_reason,
            'extra': self.extra,
        }
