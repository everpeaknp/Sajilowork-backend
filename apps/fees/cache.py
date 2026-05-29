"""In-memory cache for active fee rules (invalidated on rule save/delete)."""

from django.core.cache import cache

CACHE_KEY = 'fees:active_rules:v1'
CACHE_TTL = 300  # 5 minutes fallback if signals miss invalidation


def invalidate_fee_rules_cache():
    cache.delete(CACHE_KEY)


def get_cached_active_rules():
    from .models import FeeRule

    rules = cache.get(CACHE_KEY)
    if rules is not None:
        return rules

    rules = list(
        FeeRule.objects.filter(is_active=True)
        .select_related('category')
        .order_by('-priority', 'fee_type')
    )
    cache.set(CACHE_KEY, rules, CACHE_TTL)
    return rules
