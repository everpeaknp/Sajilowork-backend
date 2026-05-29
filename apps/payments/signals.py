from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
import logging

from .models import Payment, Refund, Payout, Transaction

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Payment)
def payment_status_changed(sender, instance, created, **kwargs):
    """
    Handle payment status changes
    """
    if not created and instance.status == 'succeeded':
        # Send notification to payer
        logger.info(f"Payment {instance.id} succeeded")
        
        # TODO: Send notification via notifications app
        # from apps.notifications.services import NotificationService
        # NotificationService.send_notification(
        #     user=instance.payer,
        #     notification_type='payment_succeeded',
        #     title='Payment Successful',
        #     message=f'Your payment of {instance.amount} {instance.currency} was successful',
        #     related_object=instance
        # )
        
        # Send notification to payee
        if instance.payee:
            logger.info(f"Notifying payee {instance.payee.id} of payment {instance.id}")
            # TODO: Send notification


@receiver(post_save, sender=Payment)
def payment_failed(sender, instance, created, **kwargs):
    """
    Handle failed payments
    """
    if not created and instance.status == 'failed':
        logger.warning(f"Payment {instance.id} failed: {instance.failure_reason}")
        
        # TODO: Send notification to payer
        # from apps.notifications.services import NotificationService
        # NotificationService.send_notification(
        #     user=instance.payer,
        #     notification_type='payment_failed',
        #     title='Payment Failed',
        #     message=f'Your payment of {instance.amount} {instance.currency} failed',
        #     related_object=instance
        # )


@receiver(post_save, sender=Refund)
def refund_processed(sender, instance, created, **kwargs):
    """
    Handle refund processing
    """
    if not created and instance.status == 'succeeded':
        logger.info(f"Refund {instance.id} succeeded")
        
        # TODO: Send notifications to both parties
        # from apps.notifications.services import NotificationService
        # NotificationService.send_notification(
        #     user=instance.payment.payer,
        #     notification_type='refund_processed',
        #     title='Refund Processed',
        #     message=f'Your refund of {instance.amount} {instance.currency} has been processed',
        #     related_object=instance
        # )


@receiver(post_save, sender=Payout)
def payout_processed(sender, instance, created, **kwargs):
    """
    Handle payout processing
    """
    if not created and instance.status == 'paid':
        logger.info(f"Payout {instance.id} completed")
        
        # TODO: Send notification to user
        # from apps.notifications.services import NotificationService
        # NotificationService.send_notification(
        #     user=instance.user,
        #     notification_type='payout_completed',
        #     title='Payout Completed',
        #     message=f'Your payout of {instance.amount} {instance.currency} has been processed',
        #     related_object=instance
        # )


@receiver(post_save, sender=Payout)
def payout_failed(sender, instance, created, **kwargs):
    """
    Handle failed payouts
    """
    if not created and instance.status == 'failed':
        logger.warning(f"Payout {instance.id} failed: {instance.failure_reason}")
        
        # Restore user balance
        if instance.user:
            instance.user.wallet_balance += instance.amount
            instance.user.save()
            logger.info(f"Restored {instance.amount} to user {instance.user.id} wallet")
        
        # TODO: Send notification to user
        # from apps.notifications.services import NotificationService
        # NotificationService.send_notification(
        #     user=instance.user,
        #     notification_type='payout_failed',
        #     title='Payout Failed',
        #     message=f'Your payout of {instance.amount} {instance.currency} failed. Your balance has been restored.',
        #     related_object=instance
        # )


@receiver(pre_save, sender=Payment)
def calculate_payment_fees(sender, instance, **kwargs):
    """
    Calculate fees before saving payment
    """
    if instance.net_amount is None and instance.amount:
        from .services import PaymentService
        fees = PaymentService.calculate_fees(instance.amount)
        instance.platform_fee = fees['platform_fee']
        instance.payment_processing_fee = fees['payment_processing_fee']
        instance.net_amount = fees['net_amount']


@receiver(post_save, sender=Payment)
def handle_escrow_release(sender, instance, created, **kwargs):
    """
    Handle automatic escrow release
    """
    if not created and instance.is_escrowed and instance.escrow_release_scheduled_at:
        if instance.escrow_release_scheduled_at <= timezone.now():
            instance.is_escrowed = False
            instance.escrow_released_at = timezone.now()
            instance.save()
            logger.info(f"Escrow released for payment {instance.id}")
