"""Keep user ratings and visibility in sync with reviews."""
from django.db.models import Avg
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from .constants import VISIBILITY_DELAY_24H
from .models import Review, ReviewPlatformSettings
from .services import ReviewService


@receiver(post_save, sender=Review)
def on_review_saved(sender, instance, created, **kwargs):
    ReviewService.update_user_profile_stats(instance.reviewee)
    if created:
        ReviewService.refresh_task_review_visibility(instance.task)


@receiver(post_delete, sender=Review)
def on_review_deleted(sender, instance, **kwargs):
    try:
        ReviewService.update_user_profile_stats(instance.reviewee)
    except Exception:
        pass


def publish_delayed_reviews():
    """Call from Celery/cron: flip is_public for delay_24h reviews past visible_at."""
    settings = ReviewPlatformSettings.get_solo()
    if settings.visibility_mode != VISIBILITY_DELAY_24H:
        return 0
    now = timezone.now()
    updated = Review.objects.filter(
        is_public=False,
        visible_at__lte=now,
        is_approved=True,
    ).update(is_public=True)
    return updated
