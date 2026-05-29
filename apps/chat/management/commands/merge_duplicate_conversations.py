"""
Merge duplicate chat threads (same bid or same task + same participants).
"""
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from apps.chat.messaging_policy import get_conversation_task
from apps.chat.models import Conversation, Message


def conversation_group_key(conversation):
    """Group key: same participants + same resolved task (via task or bid)."""
    task = get_conversation_task(conversation)
    if not task:
        return None
    participant_ids = tuple(
        sorted(conversation.participants.values_list('id', flat=True))
    )
    if len(participant_ids) < 2:
        return None
    return (str(task.id), participant_ids)


def pick_canonical(conversations):
    """Prefer thread with task+bid, then most messages, then latest activity."""

    def score(conv):
        has_task = 1 if conv.task_id else 0
        has_bid = 1 if conv.bid_id else 0
        msg_count = getattr(conv, 'message_count', 0) or 0
        last = conv.last_message_at or conv.created_at
        return (has_task + has_bid, has_task, has_bid, msg_count, last)

    return max(conversations, key=score)


class Command(BaseCommand):
    help = 'Merge duplicate conversations and deactivate extra threads'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be merged without writing',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        qs = (
            Conversation.objects.filter(is_active=True)
            .prefetch_related('participants', 'task', 'bid', 'bid__task')
            .annotate(message_count=Count('messages'))
        )

        by_bid = defaultdict(list)
        by_task_participants = defaultdict(list)

        for conv in qs:
            if conv.bid_id:
                by_bid[str(conv.bid_id)].append(conv)
            key = conversation_group_key(conv)
            if key:
                by_task_participants[key].append(conv)

        merge_groups = []

        for bid_id, convs in by_bid.items():
            if len(convs) > 1:
                merge_groups.append(convs)

        for key, convs in by_task_participants.items():
            if len(convs) > 1:
                ids = {str(c.id) for c in convs}
                already = [
                    g for g in merge_groups if ids & {str(x.id) for x in g}
                ]
                if not already:
                    merge_groups.append(convs)

        if not merge_groups:
            self.stdout.write(self.style.SUCCESS('No duplicate conversation groups found.'))
            return

        merged = 0
        for group in merge_groups:
            canonical = pick_canonical(group)
            duplicates = [c for c in group if c.id != canonical.id]
            self.stdout.write(
                f'Keep {canonical.id} (task={canonical.task_id}, bid={canonical.bid_id}), '
                f'merge {len(duplicates)} duplicate(s)'
            )
            if dry_run:
                continue

            with transaction.atomic():
                for dup in duplicates:
                    Message.objects.filter(conversation=dup).update(
                        conversation=canonical
                    )
                    dup.is_active = False
                    dup.save(update_fields=['is_active'])
                    merged += 1

                update_fields = []
                if not canonical.task_id:
                    task = get_conversation_task(canonical) or get_conversation_task(
                        duplicates[0]
                    )
                    if task:
                        canonical.task = task
                        update_fields.append('task')
                if not canonical.bid_id:
                    for dup in duplicates:
                        if dup.bid_id:
                            canonical.bid_id = dup.bid_id
                            update_fields.append('bid')
                            break
                if update_fields:
                    canonical.save(update_fields=list(dict.fromkeys(update_fields)))

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run — no changes written.'))
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Deactivated {merged} duplicate conversation(s).')
            )
