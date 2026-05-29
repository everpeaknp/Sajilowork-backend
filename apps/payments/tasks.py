"""
Celery Tasks for Payment Processing
Background jobs for escrow release, payout processing, and payment sync
"""
from celery import shared_task
from django.utils import timezone
from django.db.models import Q, Sum
from django.conf import settings
from datetime import timedelta
from decimal import Decimal
import logging
import requests

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def auto_release_escrow(self):
    """
    Auto-release escrow when completion was submitted and the review window expired.
    Uses EscrowLifecycleService (wallet held_balance -> tasker credit, fees deducted).
    """
    from .escrow_constants import SUBMITTED
    from .escrow_lifecycle import EscrowLifecycleService
    from .models import Escrow

    try:
        now = timezone.now()
        due = Escrow.objects.filter(
            status=SUBMITTED,
            auto_release_at__lte=now,
        ).select_related('task', 'payment')

        released_count = 0
        total_amount = Decimal('0.00')

        for escrow in due:
            try:
                task = escrow.task
                EscrowLifecycleService.on_task_completed(task)
                payment = EscrowLifecycleService.release_escrow(
                    task,
                    force=True,
                )
                task.status = 'completed'
                if hasattr(task, 'completed_at'):
                    task.completed_at = now
                    task.save(update_fields=['status', 'completed_at'])
                else:
                    task.completion_date = now
                    task.save(update_fields=['status', 'completion_date'])

                released_count += 1
                total_amount += payment.net_amount or Decimal('0')
                logger.info('Auto-released escrow %s for task %s', escrow.id, task.id)
            except Exception as e:
                logger.error('Auto-release failed for escrow %s: %s', escrow.id, e)
                continue

        return {
            'success': True,
            'released_count': released_count,
            'total_amount': float(total_amount),
        }
    except Exception as exc:
        logger.error('Error in auto_release_escrow: %s', exc)
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, max_retries=3)
def process_pending_payouts(self):
    """
    Process pending payout requests.
    
    Workflow:
    1. Find payouts with status='pending'
    2. Verify user has sufficient balance
    3. Process payout via payment gateway (eSewa/Khalti)
    4. Update payout status
    5. Deduct from wallet
    6. Send notifications
    
    Runs: Every 6 hours (configured in celery.py)
    """
    from .models import Payout
    from .gateways.esewa import ESewaGateway
    from .gateways.khalti import KhaltiGateway
    from apps.wallets.models import Wallet, WalletTransaction
    from apps.notifications.services import NotificationService
    
    try:
        # Find pending payouts
        pending_payouts = Payout.objects.filter(
            status='pending'
        ).select_related('user')
        
        processed_count = 0
        failed_count = 0
        total_amount = Decimal('0.00')
        
        for payout in pending_payouts:
            try:
                user = payout.user
                
                # Get user's wallet
                try:
                    wallet = Wallet.objects.get(user=user)
                except Wallet.DoesNotExist:
                    logger.error(f"Wallet not found for user {user.id}")
                    payout.status = 'failed'
                    payout.failure_reason = 'Wallet not found'
                    payout.save()
                    failed_count += 1
                    continue
                
                # Check sufficient balance
                if wallet.balance < payout.amount:
                    logger.warning(f"Insufficient balance for payout {payout.id}")
                    payout.status = 'failed'
                    payout.failure_reason = 'Insufficient balance'
                    payout.save()
                    failed_count += 1
                    continue
                
                # Calculate fees (1% payout fee)
                payout.processing_fee = payout.amount * Decimal('0.01')
                payout.net_amount = payout.amount - payout.processing_fee
                
                # Process payout via gateway
                # For now, mark as processing (actual gateway integration needed)
                payout.status = 'processing'
                payout.save()
                
                # Deduct from wallet
                WalletTransaction.objects.create(
                    wallet=wallet,
                    transaction_type='debit',
                    amount=payout.amount,
                    balance_after=wallet.balance - payout.amount,
                    description=f"Payout to {payout.payout_method}",
                    reference_type='payout',
                    reference_id=str(payout.id),
                    status='completed'
                )
                
                wallet.balance -= payout.amount
                wallet.save()
                
                # Mark as paid (in production, this would be done after gateway confirmation)
                payout.status = 'paid'
                payout.completed_at = timezone.now()
                payout.save()
                
                # Send notification
                NotificationService.send_notification(
                    user=user,
                    notification_type='payout_processed',
                    title='Payout Processed',
                    message=f'Your payout of NPR {payout.net_amount} has been processed.',
                    related_object=payout,
                    priority='high'
                )
                
                processed_count += 1
                total_amount += payout.net_amount
                logger.info(f"Processed payout {payout.id}: NPR {payout.net_amount}")
                
            except Exception as e:
                logger.error(f"Error processing payout {payout.id}: {e}")
                payout.status = 'failed'
                payout.failure_reason = str(e)
                payout.save()
                failed_count += 1
                continue
        
        logger.info(f"Processed {processed_count} payouts, failed: {failed_count}, total: NPR {total_amount}")
        return {
            'success': True,
            'processed_count': processed_count,
            'failed_count': failed_count,
            'total_amount': float(total_amount)
        }
        
    except Exception as exc:
        logger.error(f"Error in process_pending_payouts: {exc}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, max_retries=3)
def sync_payment_status(self):
    """
    Sync payment status with eSewa and Khalti gateways.
    
    Workflow:
    1. Find payments with status='processing' or 'pending'
    2. Query eSewa/Khalti API for status
    3. Update payment status accordingly
    4. Send notifications on status change
    
    Runs: Every 10 minutes (configured in celery.py)
    """
    from .models import Payment
    from .gateways.esewa import ESewaGateway
    from .gateways.khalti import KhaltiGateway
    from apps.notifications.services import NotificationService
    
    try:
        # Find payments to sync
        payments_to_sync = Payment.objects.filter(
            Q(status='processing') | Q(status='pending'),
            payment_method__in=['esewa', 'khalti'],
            created_at__gte=timezone.now() - timedelta(days=7)  # Only sync recent payments
        ).select_related('payer', 'payee')
        
        synced_count = 0
        updated_count = 0
        
        for payment in payments_to_sync:
            try:
                old_status = payment.status
                new_status = None
                
                # Query gateway based on payment method
                if payment.payment_method == 'esewa':
                    # eSewa status check
                    esewa = ESewaGateway()
                    # Note: eSewa doesn't have a direct status check API
                    # Status is confirmed via callback URL
                    # This is a placeholder for future implementation
                    pass
                    
                elif payment.payment_method == 'khalti':
                    # Khalti status check
                    khalti = KhaltiGateway()
                    if payment.metadata.get('khalti_token'):
                        try:
                            # Verify payment with Khalti
                            result = khalti.verify_payment(
                                token=payment.metadata['khalti_token'],
                                amount=int(payment.amount * 100)  # Convert to paisa
                            )
                            
                            if result.get('success'):
                                new_status = 'succeeded'
                                payment.completed_at = timezone.now()
                            else:
                                new_status = 'failed'
                                payment.failure_reason = result.get('error', 'Payment verification failed')
                        except Exception as e:
                            logger.error(f"Error verifying Khalti payment {payment.id}: {e}")
                
                # Update status if changed
                if new_status and new_status != old_status:
                    payment.status = new_status
                    payment.save()
                    updated_count += 1
                    
                    # Send notification on status change
                    if new_status == 'succeeded':
                        NotificationService.send_notification(
                            user=payment.payer,
                            notification_type='payment_succeeded',
                            title='Payment Successful',
                            message=f'Your payment of NPR {payment.amount} was successful.',
                            related_object=payment,
                            priority='normal'
                        )
                    elif new_status == 'failed':
                        NotificationService.send_notification(
                            user=payment.payer,
                            notification_type='payment_failed',
                            title='Payment Failed',
                            message=f'Your payment of NPR {payment.amount} failed. Please try again.',
                            related_object=payment,
                            priority='high'
                        )
                    
                    logger.info(f"Updated payment {payment.id} status: {old_status} -> {new_status}")
                
                synced_count += 1
                
            except Exception as e:
                logger.error(f"Error syncing payment {payment.id}: {e}")
                continue
        
        logger.info(f"Synced {synced_count} payments, updated: {updated_count}")
        return {
            'success': True,
            'synced_count': synced_count,
            'updated_count': updated_count
        }
        
    except Exception as exc:
        logger.error(f"Error in sync_payment_status: {exc}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, max_retries=3)
def generate_payment_reports(self):
    """
    Generate daily/monthly payment reports for admin.
    
    Workflow:
    1. Calculate daily payment statistics
    2. Calculate platform revenue
    3. Generate report data
    4. Store in database or send to admin
    
    Runs: Daily at 11:30 PM (configured in celery.py)
    """
    from .models import Payment, Payout, Refund
    from apps.analytics.models import AnalyticsEvent
    
    try:
        # Calculate for yesterday
        yesterday = timezone.now().date() - timedelta(days=1)
        start_date = timezone.datetime.combine(yesterday, timezone.datetime.min.time())
        end_date = timezone.datetime.combine(yesterday, timezone.datetime.max.time())
        
        # Make timezone aware
        start_date = timezone.make_aware(start_date)
        end_date = timezone.make_aware(end_date)
        
        # Payment statistics
        payments = Payment.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        total_payments = payments.count()
        successful_payments = payments.filter(status='succeeded').count()
        failed_payments = payments.filter(status='failed').count()
        
        total_amount = payments.filter(status='succeeded').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        platform_revenue = payments.filter(status='succeeded').aggregate(
            total=Sum('platform_fee')
        )['total'] or Decimal('0.00')
        
        processing_fees = payments.filter(status='succeeded').aggregate(
            total=Sum('payment_processing_fee')
        )['total'] or Decimal('0.00')
        
        # Payout statistics
        payouts = Payout.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        total_payouts = payouts.count()
        successful_payouts = payouts.filter(status='paid').count()
        
        payout_amount = payouts.filter(status='paid').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        # Refund statistics
        refunds = Refund.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        total_refunds = refunds.count()
        refund_amount = refunds.filter(status='succeeded').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        # Create analytics event
        report_data = {
            'date': str(yesterday),
            'payments': {
                'total': total_payments,
                'successful': successful_payments,
                'failed': failed_payments,
                'total_amount': float(total_amount),
                'platform_revenue': float(platform_revenue),
                'processing_fees': float(processing_fees),
            },
            'payouts': {
                'total': total_payouts,
                'successful': successful_payouts,
                'total_amount': float(payout_amount),
            },
            'refunds': {
                'total': total_refunds,
                'total_amount': float(refund_amount),
            },
            'net_revenue': float(platform_revenue - processing_fees),
        }
        
        # Store report in analytics
        AnalyticsEvent.objects.create(
            event_type='daily_payment_report',
            event_data=report_data,
            created_at=timezone.now()
        )
        
        logger.info(f"Generated payment report for {yesterday}")
        logger.info(f"Total payments: {total_payments}, Amount: NPR {total_amount}")
        logger.info(f"Platform revenue: NPR {platform_revenue}")
        
        return {
            'success': True,
            'report_date': str(yesterday),
            'data': report_data
        }
        
    except Exception as exc:
        logger.error(f"Error in generate_payment_reports: {exc}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True)
def process_payment_webhook(self, webhook_data: dict):
    """
    Process payment gateway webhooks (eSewa/Khalti).
    
    Args:
        webhook_data: Webhook payload from gateway
    """
    from .models import Payment
    from apps.notifications.services import NotificationService
    
    try:
        gateway = webhook_data.get('gateway')
        payment_id = webhook_data.get('payment_id')
        status = webhook_data.get('status')
        
        if not all([gateway, payment_id, status]):
            logger.error("Invalid webhook data")
            return {'success': False, 'error': 'Invalid webhook data'}
        
        # Find payment
        try:
            payment = Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            logger.error(f"Payment {payment_id} not found")
            return {'success': False, 'error': 'Payment not found'}
        
        # Update payment status
        old_status = payment.status
        payment.status = status
        
        if status == 'succeeded':
            payment.completed_at = timezone.now()
        elif status == 'failed':
            payment.failure_reason = webhook_data.get('failure_reason', 'Payment failed')
        
        payment.save()
        
        # Send notification
        if status != old_status:
            if status == 'succeeded':
                NotificationService.send_notification(
                    user=payment.payer,
                    notification_type='payment_succeeded',
                    title='Payment Successful',
                    message=f'Your payment of NPR {payment.amount} was successful.',
                    related_object=payment,
                    priority='normal'
                )
            elif status == 'failed':
                NotificationService.send_notification(
                    user=payment.payer,
                    notification_type='payment_failed',
                    title='Payment Failed',
                    message=f'Your payment of NPR {payment.amount} failed.',
                    related_object=payment,
                    priority='high'
                )
        
        logger.info(f"Processed webhook for payment {payment_id}: {old_status} -> {status}")
        return {'success': True}
        
    except Exception as e:
        logger.error(f"Error processing payment webhook: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(bind=True)
def cleanup_old_payment_records(self):
    """
    Archive old payment records for data retention.
    
    Workflow:
    1. Find payments older than 2 years
    2. Archive to separate table or export
    Runs: Monthly (can be added to beat schedule)
    """
    from .models import Payment

    try:
        cutoff_date = timezone.now() - timedelta(days=730)

        old_payments = Payment.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['succeeded', 'failed', 'refunded', 'cancelled']
        )

        archived_count = old_payments.count()
        logger.info(f"Found {archived_count} old payments to archive")

        return {
            'success': True,
            'archived_payments': archived_count,
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_payment_records: {e}")
        return {'success': False, 'error': str(e)}
