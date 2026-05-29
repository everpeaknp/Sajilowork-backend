"""
Tasker tier resolution based on rolling 30-day earnings (Airtasker-style).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

TASKER_TIERS: list[dict[str, Any]] = [
    {
        'slug': 'bronze',
        'name': 'Bronze',
        'min_earnings': Decimal('0'),
        'service_fee_percent': Decimal('20.0'),
    },
    {
        'slug': 'silver',
        'name': 'Silver',
        'min_earnings': Decimal('880'),
        'service_fee_percent': Decimal('18.5'),
    },
    {
        'slug': 'gold',
        'name': 'Gold',
        'min_earnings': Decimal('2650'),
        'service_fee_percent': Decimal('16.0'),
    },
    {
        'slug': 'platinum',
        'name': 'Platinum',
        'min_earnings': Decimal('5300'),
        'service_fee_percent': Decimal('14.0'),
    },
]


def _serialize_tier(tier: dict[str, Any]) -> dict[str, Any]:
    return {
        'slug': tier['slug'],
        'name': tier['name'],
        'min_earnings': float(tier['min_earnings']),
        'service_fee_percent': float(tier['service_fee_percent']),
    }


def resolve_tasker_tier(earnings_last_30_days: Decimal | float | int) -> dict[str, Any]:
    """Return current tier, next tier, progress, and milestone markers."""
    earnings = Decimal(str(earnings_last_30_days or 0))

    current = TASKER_TIERS[0]
    for tier in TASKER_TIERS:
        if earnings >= tier['min_earnings']:
            current = tier
        else:
            break

    current_index = TASKER_TIERS.index(current)
    next_tier: Optional[dict[str, Any]] = (
        TASKER_TIERS[current_index + 1] if current_index + 1 < len(TASKER_TIERS) else None
    )

    if next_tier:
        range_size = next_tier['min_earnings'] - current['min_earnings']
        earned_in_range = earnings - current['min_earnings']
        progress = float((earned_in_range / range_size) * 100) if range_size > 0 else 0.0
        amount_to_next = float(max(Decimal('0'), next_tier['min_earnings'] - earnings))
    else:
        progress = 100.0
        amount_to_next = 0.0

    return {
        'current': _serialize_tier(current),
        'next': _serialize_tier(next_tier) if next_tier else None,
        'earnings_last_30_days': float(earnings),
        'amount_to_next_tier': amount_to_next,
        'progress_to_next_tier_percent': min(100.0, max(0.0, progress)),
        'milestones': [
            {
                'slug': tier['slug'],
                'name': tier['name'],
                'min_earnings': float(tier['min_earnings']),
            }
            for tier in TASKER_TIERS
        ],
    }
