"""Username change cooldown policy (once per 6 months)."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

USERNAME_CHANGE_COOLDOWN = timedelta(days=183)


def normalize_username(value: str) -> str:
    return (value or '').strip().lower()


def usernames_equal(a: str | None, b: str | None) -> bool:
    return normalize_username(a or '') == normalize_username(b or '')


def get_username_change_status(user):
    """
    Returns (can_change, next_change_at).
    next_change_at is set only when the user must wait.
    """
    changed_at = getattr(user, 'username_changed_at', None)
    if not changed_at:
        return True, None

    next_change_at = changed_at + USERNAME_CHANGE_COOLDOWN
    if timezone.now() >= next_change_at:
        return True, None
    return False, next_change_at


def assert_username_change_allowed(user, new_username: str) -> None:
    """Raise ValueError with a user-facing message if change is not allowed."""
    from rest_framework import serializers

    if usernames_equal(user.username, new_username):
        return

    can_change, next_change_at = get_username_change_status(user)
    if can_change:
        return

    date_label = next_change_at.strftime('%d %b %Y') if next_change_at else 'later'
    raise serializers.ValidationError(
        {
            'username': [
                f'You can only change your username once every 6 months. '
                f'You can change it again on {date_label}.'
            ]
        }
    )
