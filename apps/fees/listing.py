"""Map tasks to fee rule listing_kind values."""

from apps.tasks.listing import LISTING_KIND_TASK, get_listing_kind


def fee_listing_kind_for_task(task) -> str:
    """Resolve listing kind for fee rules (defaults to marketplace task)."""
    if task is None:
        return LISTING_KIND_TASK
    tags = getattr(task, 'tags', None)
    kind = get_listing_kind(tags)
    return kind or LISTING_KIND_TASK
