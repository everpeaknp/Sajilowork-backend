from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.notifications.services import NotificationService
from apps.tasks.models import Task

from .models import AccountSuspensionLog, PlatformRule

User = get_user_model()


class ModerationService:
    """Enforce platform rules (auto-suspend on excess cancellations, etc.)."""

    @staticmethod
    def get_active_auto_suspend_rule() -> PlatformRule | None:
        return (
            PlatformRule.objects.filter(
                rule_type=PlatformRule.RuleType.AUTO_SUSPEND_EXCESS_CANCELLATIONS,
                is_active=True,
            )
            .first()
        )

    @staticmethod
    def rule_applies_to_user(rule: PlatformRule, user: User) -> bool:
        if user.role == 'customer' and rule.applies_to_customers:
            return True
        if user.role == 'tasker' and rule.applies_to_taskers:
            return True
        # Users with role 'both' or edge cases: apply if either flag is on
        if user.role not in ('customer', 'tasker'):
            return rule.applies_to_customers or rule.applies_to_taskers
        return False

    @staticmethod
    def count_user_cancellations(user: User, rule: PlatformRule) -> int:
        qs = Task.objects.filter(status='cancelled', cancelled_by=user)
        if rule.counting_window_days:
            since = timezone.now() - timedelta(days=rule.counting_window_days)
            qs = qs.filter(cancelled_at__gte=since)
        return qs.count()

    @staticmethod
    def refresh_suspension_state(user: User) -> User:
        """Clear expired suspensions; return user with up-to-date flags."""
        if not user.account_suspended:
            return user

        until = getattr(user, 'suspended_until', None)
        if until and timezone.now() >= until:
            user.account_suspended = False
            user.suspended_until = None
            user.suspension_reason = ''
            user.save(update_fields=['account_suspended', 'suspended_until', 'suspension_reason'])
            AccountSuspensionLog.objects.filter(
                user=user,
                lifted_at__isnull=True,
                suspended_until__lte=timezone.now(),
            ).update(lifted_at=timezone.now())
        return user

    @staticmethod
    def is_user_suspended(user: User) -> bool:
        user = ModerationService.refresh_suspension_state(user)
        return bool(user.account_suspended)

    @staticmethod
    @transaction.atomic
    def apply_auto_suspend_if_needed(user: User) -> dict | None:
        """
        After a cancellation, check threshold and suspend if exceeded.
        Returns suspension info dict or None.
        """
        rule = ModerationService.get_active_auto_suspend_rule()
        if not rule or not ModerationService.rule_applies_to_user(rule, user):
            return None

        count = ModerationService.count_user_cancellations(user, rule)
        if count <= rule.max_cancellations:
            return None

        if ModerationService.is_user_suspended(user):
            return None

        suspended_until = timezone.now() + timedelta(hours=rule.suspension_hours)
        reason = (
            f'Account suspended for {rule.suspension_hours} hours: '
            f'more than {rule.max_cancellations} task cancellations '
            f'({"last " + str(rule.counting_window_days) + " days" if rule.counting_window_days else "all time"}).'
        )

        user.account_suspended = True
        user.suspended_until = suspended_until
        user.suspension_reason = reason
        user.save(update_fields=['account_suspended', 'suspended_until', 'suspension_reason'])

        AccountSuspensionLog.objects.create(
            user=user,
            rule=rule,
            cancellation_count=count,
            suspended_until=suspended_until,
            reason=reason,
        )

        NotificationService.send_notification(
            user=user,
            notification_type='account_suspended',
            title='Account temporarily suspended',
            message=reason,
            data={
                'suspended_until': suspended_until.isoformat(),
                'cancellation_count': count,
                'max_cancellations': rule.max_cancellations,
            },
        )

        return {
            'suspended': True,
            'suspended_until': suspended_until,
            'cancellation_count': count,
            'reason': reason,
        }

    @staticmethod
    def on_task_cancelled(user: User) -> dict | None:
        """Hook after a user cancels a task."""
        return ModerationService.apply_auto_suspend_if_needed(user)
