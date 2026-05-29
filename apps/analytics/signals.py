"""
Signal handlers for Analytics app.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Cohort


@receiver(post_save, sender=Cohort)
def update_cohort_member_count(sender, instance, created, **kwargs):
    """Update cohort member count after save."""
    if not created:
        instance.member_count = instance.users.count()
        instance.save(update_fields=['member_count'])
