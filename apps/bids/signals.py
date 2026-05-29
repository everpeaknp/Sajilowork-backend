"""
Signal handlers for Bids app.
"""
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db.models import Avg
from .models import Bid, BidMessage, BidReview, BidNotification


@receiver(post_save, sender=Bid)
def update_task_bid_count(sender, instance, created, **kwargs):
    """
    Update task bid count when a bid is created or updated.
    """
    if created:
        # Increment bid count
        task = instance.task
        task.bids_count = task.bids.filter(status='pending').count()
        task.save(update_fields=['bids_count'])


@receiver(post_delete, sender=Bid)
def decrement_task_bid_count(sender, instance, **kwargs):
    """
    Decrement task bid count when a bid is deleted.
    """
    try:
        task = instance.task
        # Check if task still exists (might be deleted via CASCADE)
        if task and task.pk:
            task.bids_count = task.bids.filter(status='pending').count()
            task.save(update_fields=['bids_count'])
    except Exception:
        # Task was deleted or doesn't exist anymore, skip update
        pass


@receiver(post_save, sender=Bid)
def update_tasker_stats_on_bid_status_change(sender, instance, created, **kwargs):
    """
    Update tasker statistics when bid status changes.
    """
    if not created:
        # Check if status changed to accepted
        if instance.status == 'accepted':
            tasker = instance.tasker
            
            # Update accepted bids count (can be calculated from bids)
            accepted_bids = Bid.objects.filter(
                tasker=tasker,
                status='accepted'
            ).count()
            
            # Calculate acceptance rate
            total_bids = Bid.objects.filter(tasker=tasker).count()
            if total_bids > 0:
                acceptance_rate = (accepted_bids / total_bids) * 100
                tasker.completion_rate = round(acceptance_rate, 2)
                tasker.save(update_fields=['completion_rate'])


@receiver(post_save, sender=BidReview)
def update_tasker_rating_from_bid_review(sender, instance, created, **kwargs):
    """
    Update tasker's average rating when a bid review is created.
    Note: This is for bid reviews, not task completion reviews.
    """
    if created:
        tasker = instance.bid.tasker
        
        # Calculate average rating from bid reviews
        avg_rating = BidReview.objects.filter(
            bid__tasker=tasker
        ).aggregate(Avg('rating'))['rating__avg']
        
        if avg_rating:
            # Update tasker's rating (you might want a separate field for bid ratings)
            # For now, we'll just track it in the review count
            review_count = BidReview.objects.filter(bid__tasker=tasker).count()
            
            # You can add a custom field to User model for bid_rating if needed
            # tasker.bid_rating = avg_rating
            # tasker.bid_review_count = review_count
            # tasker.save(update_fields=['bid_rating', 'bid_review_count'])


@receiver(post_save, sender=BidMessage)
def send_bid_message_notification(sender, instance, created, **kwargs):
    """
    Send notification when a new bid message is created.
    This is handled in the view, but kept here as backup.
    """
    if created:
        # Determine recipient (opposite party)
        recipient = (
            instance.bid.task.owner
            if instance.sender == instance.bid.tasker
            else instance.bid.tasker
        )
        
        # Check if notification already exists (to avoid duplicates)
        existing = BidNotification.objects.filter(
            bid=instance.bid,
            recipient=recipient,
            notification_type='bid_message',
            created_at=instance.created_at
        ).exists()
        
        if not existing:
            BidNotification.objects.create(
                bid=instance.bid,
                recipient=recipient,
                notification_type='bid_message',
                message=f"New message from {instance.sender.get_full_name()} on bid for '{instance.bid.task.title}'"
            )


@receiver(pre_save, sender=Bid)
def track_bid_status_changes(sender, instance, **kwargs):
    """
    Track bid status changes and create notifications.
    """
    if instance.pk:  # Only for updates, not new bids
        try:
            old_instance = Bid.objects.get(pk=instance.pk)
            
            # Check if status changed
            if old_instance.status != instance.status:
                # Status changed - notification will be created in view
                # This is just for tracking/logging
                pass
        
        except Bid.DoesNotExist:
            pass


@receiver(post_save, sender=Bid)
def auto_accept_bid_if_enabled(sender, instance, created, **kwargs):
    """
    Automatically accept bid if task has auto_accept_bid enabled
    and bid meets criteria.
    """
    if created and instance.task.auto_accept_bid:
        # Check if bid amount matches task budget
        if instance.amount <= instance.task.budget_amount:
            try:
                instance.accept()
            except ValueError:
                # Bid cannot be accepted (maybe task already assigned)
                pass


@receiver(post_save, sender=Bid)
def check_and_expire_old_bids(sender, instance, created, **kwargs):
    """
    Check and expire old pending bids on the same task.
    This can be moved to a Celery periodic task for better performance.
    """
    from django.utils import timezone
    from datetime import timedelta
    
    if created:
        # Expire bids older than 30 days
        expiry_date = timezone.now() - timedelta(days=30)
        
        Bid.objects.filter(
            task=instance.task,
            status='pending',
            created_at__lt=expiry_date
        ).update(status='expired')


@receiver(post_delete, sender=BidNotification)
def cleanup_orphaned_notifications(sender, instance, **kwargs):
    """
    Cleanup logic when notifications are deleted.
    Currently just a placeholder for future cleanup tasks.
    """
    pass


# Optional: Send email notifications
@receiver(post_save, sender=BidNotification)
def send_email_notification_for_bid(sender, instance, created, **kwargs):
    """
    Send email notification when a bid notification is created.
    This should be moved to a Celery task for async processing.
    """
    if created and instance.recipient.email_notifications:
        # TODO: Implement email sending via Celery
        # from apps.notifications.tasks import send_bid_notification_email
        # send_bid_notification_email.delay(instance.id)
        pass
