"""Bookmark business logic shared by tasks and bookmark APIs."""
from uuid import UUID

from django.shortcuts import get_object_or_404

from apps.tasks.listing import (
    LISTING_KIND_CHOICES,
    LISTING_KIND_TASK,
    filter_queryset_by_listing_kind,
    filter_queryset_plain_tasks,
    get_listing_kind,
)
from apps.tasks.models import Task, TaskBookmark


def get_bookmarkable_task(slug: str) -> Task:
    normalized = (slug or '').strip()
    if not normalized:
        raise Task.DoesNotExist
    try:
        return Task.objects.get(slug=normalized)
    except Task.DoesNotExist:
        pass
    try:
        UUID(normalized)
    except ValueError:
        return get_object_or_404(Task, slug=normalized)
    return get_object_or_404(Task, pk=normalized)


def add_bookmark(user, task: Task) -> tuple[TaskBookmark, bool]:
    """Create bookmark; signals maintain bookmarks_count."""
    return TaskBookmark.objects.get_or_create(user=user, task=task)


def remove_bookmark(user, task: Task) -> bool:
    """Remove bookmark if present. Returns True when deleted."""
    deleted_count, _ = TaskBookmark.objects.filter(user=user, task=task).delete()
    return deleted_count > 0


def list_bookmarked_tasks(user, listing_kind: str | None = None):
    queryset = (
        Task.objects.filter(bookmarks__user=user)
        .select_related('owner', 'owner__employer_profile', 'category', 'assigned_tasker')
        .prefetch_related('attachments')
        .order_by('-bookmarks__created_at')
        .distinct()
    )
    if listing_kind in LISTING_KIND_CHOICES:
        queryset = filter_queryset_by_listing_kind(queryset, listing_kind)
    elif listing_kind == LISTING_KIND_TASK:
        queryset = filter_queryset_plain_tasks(queryset)
    return queryset


def user_bookmark_task_ids(user) -> set:
    if not user or not user.is_authenticated:
        return set()
    return set(TaskBookmark.objects.filter(user=user).values_list('task_id', flat=True))


def bookmark_listing_kind(task: Task) -> str:
    return get_listing_kind(task.tags)
