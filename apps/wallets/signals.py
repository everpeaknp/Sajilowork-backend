from django.conf import settings
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Wallet, WalletTransaction, WithdrawalRequest

DEFAULT_CURRENCY = getattr(settings, 'DEFAULT_CURRENCY', 'NPR')
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender='users.User')
def create_user_wallet(sender, instance, created, **kwargs):
    """
    Automatically create wallet when user is created
    """
    if created:
        Wallet.objects.get_or_create(
            user=instance,
            defaults={'currency': DEFAULT_CURRENCY},
        )
        logger.info(f"Wallet created for user {instance.email}")


@receiver(post_save, sender=WalletTransaction)
def transaction_completed(sender, instance, created, **kwargs):
    """
    Handle transaction completion
    """
    if instance.status == 'completed' and not instance.completed_at:
        instance.completed_at = timezone.now()
        instance.save(update_fields=['completed_at'])


@receiver(post_save, sender=WithdrawalRequest)
def withdrawal_status_changed(sender, instance, created, **kwargs):
    """
    Handle withdrawal request status changes
    """
    if not created:
        # Log status changes
        if instance.status == 'completed':
            logger.info(f"Withdrawal {instance.id} completed: {instance.amount} {instance.currency}")
        elif instance.status == 'failed':
            logger.error(f"Withdrawal {instance.id} failed: {instance.failure_reason}")
        elif instance.status == 'rejected':
            logger.info(f"Withdrawal {instance.id} rejected: {instance.rejection_reason}")
        
        # TODO: Send notification to user
        # from apps.notifications.services import NotificationService
        # NotificationService.send_withdrawal_status_notification(instance)


@receiver(pre_save, sender=WithdrawalRequest)
def calculate_withdrawal_fees(sender, instance, **kwargs):
    """Calculate withdrawal fees from FeeRule (admin-configurable)."""
    from apps.fees.engine import FeeEngine

    line = FeeEngine.calculate_withdrawal(
        instance.amount,
        instance.withdrawal_method or '',
    )
    instance.processing_fee = line.amount
    instance.net_amount = instance.amount - line.amount
    meta = dict(instance.metadata or {})
    meta['withdrawal_fee_rule'] = {
        'rule_id': line.rule_id,
        'rule_name': line.rule_name,
    }
    instance.metadata = meta


@receiver(post_save, sender=WithdrawalRequest)
def handle_withdrawal_completion(sender, instance, created, **kwargs):
    """
    Handle withdrawal completion
    """
    if instance.status == 'completed' and not instance.completed_at:
        instance.completed_at = timezone.now()
        instance.save(update_fields=['completed_at'])
