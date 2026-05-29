"""
Locations Signals
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import UserLocation, ServiceArea


@receiver(pre_save, sender=UserLocation)
def ensure_single_default_location(sender, instance, **kwargs):
    """Ensure only one default location per user"""
    if instance.is_default:
        # Unset other default locations for this user
        UserLocation.objects.filter(
            user=instance.user,
            is_default=True
        ).exclude(id=instance.id).update(is_default=False)


@receiver(post_save, sender=ServiceArea)
def update_user_service_area_count(sender, instance, created, **kwargs):
    """Update user's service area count (for future analytics)"""
    if created:
        # TODO: Update user profile with service area count
        # This can be used for tasker profile completeness
        pass
