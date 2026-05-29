from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .cache import invalidate_fee_rules_cache
from .models import FeeRule


@receiver(post_save, sender=FeeRule)
@receiver(post_delete, sender=FeeRule)
def clear_fee_rule_cache(sender, **kwargs):
    invalidate_fee_rules_cache()
