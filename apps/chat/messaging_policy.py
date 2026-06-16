"""
Rules for when task-linked conversations allow new messages.
"""
from __future__ import annotations

MESSAGING_ALLOWED_TASK_STATUSES = frozenset({'assigned', 'funded', 'in_progress', 'pending_approval'})


def get_conversation_task(conversation):
    """Resolve the Task linked to a conversation (directly or via bid)."""
    if getattr(conversation, 'task_id', None) and conversation.task_id:
        return conversation.task

    bid = getattr(conversation, 'bid', None)
    if bid is not None and getattr(bid, 'task_id', None):
        return bid.task

    if getattr(conversation, 'bid_id', None):
        from apps.bids.models import Bid

        bid = Bid.objects.select_related('task').filter(pk=conversation.bid_id).first()
        if bid:
            return bid.task

    return None


def task_allows_messaging(task) -> tuple[bool, str | None]:
    if task is None:
        return True, None

    if task.status in MESSAGING_ALLOWED_TASK_STATUSES:
        return True, None

    labels = dict(getattr(task, 'STATUS_CHOICES', ()))
    label = labels.get(task.status, task.status.replace('_', ' '))
    return False, f'Messaging is closed because this task is {label.lower()}.'


def conversation_allows_messaging(conversation) -> tuple[bool, str | None]:
    if not getattr(conversation, 'task_id', None) and not getattr(conversation, 'bid_id', None):
        return True, None
    return task_allows_messaging(get_conversation_task(conversation))
