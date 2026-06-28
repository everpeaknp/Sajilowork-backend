"""Celery tasks for authentication maintenance."""
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def cleanup_expired_tokens():
    """Remove expired outstanding JWT records from the blacklist tables."""
    try:
        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

        deleted, _ = OutstandingToken.objects.filter(expires_at__lt=timezone.now()).delete()
        logger.info('cleanup_expired_tokens: removed %s expired token(s)', deleted)
        return deleted
    except Exception:
        logger.exception('cleanup_expired_tokens failed')
        return 0
