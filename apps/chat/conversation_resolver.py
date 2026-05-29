"""
Find or create a single conversation thread per task/bid + participant pair.
"""
from __future__ import annotations

from django.db.models import Q

from .models import Conversation


def _participant_ids(conversation) -> set:
    return set(conversation.participants.values_list('id', flat=True))


def _resolve_task_id(*, task=None, bid=None):
    if task is not None:
        return getattr(task, 'id', task)
    if bid is not None:
        return getattr(bid, 'task_id', None)
    return None


def find_existing_conversation(
    *,
    task=None,
    bid=None,
    participant_user_ids,
    active_only: bool = True,
):
    """
    Locate an existing thread for the same people on the same task/bid.

    Matches by bid id, or by task id (including bid-only rows for that task).
    """
    participant_user_ids = {uid for uid in participant_user_ids if uid}
    if len(participant_user_ids) < 2:
        return None

    task_id = _resolve_task_id(task=task, bid=bid)
    bid_id = getattr(bid, 'id', bid) if bid is not None else None

    qs = Conversation.objects.prefetch_related('participants')
    if active_only:
        qs = qs.filter(is_active=True)

    filters = Q()
    if bid_id:
        filters |= Q(bid_id=bid_id)
    if task_id:
        filters |= Q(task_id=task_id) | Q(bid__task_id=task_id)

    if not filters:
        return None

    for conversation in qs.filter(filters).distinct():
        conv_participants = _participant_ids(conversation)
        if participant_user_ids == conv_participants:
            return conversation

    return None


def get_or_create_conversation(
    *,
    task=None,
    bid=None,
    participant_users,
    active_only: bool = True,
):
    """
    Return (conversation, created). Reuses an existing row and backfills task/bid if needed.
    """
    users = list(participant_users)
    participant_user_ids = [u.id for u in users]

    existing = find_existing_conversation(
        task=task,
        bid=bid,
        participant_user_ids=participant_user_ids,
        active_only=active_only,
    )
    if existing:
        update_fields = []
        if task is not None and not existing.task_id:
            existing.task = task
            update_fields.append('task')
        if bid is not None and not existing.bid_id:
            existing.bid = bid
            update_fields.append('bid')
        if update_fields:
            existing.save(update_fields=update_fields)
        return existing, False

    conversation = Conversation.objects.create(task=task, bid=bid)
    conversation.participants.add(*users)
    return conversation, True
