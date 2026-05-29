"""
Signal handlers for chat app.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Message, MessageReaction, MessageReport


@receiver(post_save, sender=Message)
def handle_new_message(sender, instance, created, **kwargs):
    """
    Handle new message creation.
    - Update conversation's last_message_at
    - Send notification to other participants (TODO: integrate with notifications app)
    """
    if created and not instance.is_deleted:
        # Update conversation's last_message_at
        conversation = instance.conversation
        if not conversation.last_message_at or instance.created_at > conversation.last_message_at:
            conversation.last_message_at = instance.created_at
            conversation.save(update_fields=['last_message_at'])
        
        # TODO: Send notification to other participants
        # This will be implemented when notifications app is ready
        # for participant in conversation.participants.exclude(id=instance.sender.id):
        #     create_notification(
        #         user=participant,
        #         notification_type='new_message',
        #         title=f'New message from {instance.sender.get_full_name()}',
        #         message=instance.content[:100],
        #         related_object=instance
        #     )


@receiver(post_save, sender=MessageReaction)
def handle_message_reaction(sender, instance, created, **kwargs):
    """
    Handle message reaction.
    - Send notification to message sender (TODO: integrate with notifications app)
    """
    if created:
        message = instance.message
        
        # Don't notify if user reacted to their own message
        if message.sender != instance.user:
            # TODO: Send notification to message sender
            # This will be implemented when notifications app is ready
            pass


@receiver(post_save, sender=MessageReport)
def handle_message_report(sender, instance, created, **kwargs):
    """
    Handle message report.
    - Notify admins about new report (TODO: integrate with notifications app)
    - Auto-hide message if multiple reports (TODO: implement auto-moderation)
    """
    if created:
        # TODO: Notify admins about new report
        # This will be implemented when notifications app is ready
        
        # TODO: Auto-hide message if it has multiple reports
        # report_count = MessageReport.objects.filter(message=instance.message).count()
        # if report_count >= 3:  # Threshold for auto-hiding
        #     instance.message.is_deleted = True
        #     instance.message.save(update_fields=['is_deleted'])
        pass


@receiver(post_delete, sender=Message)
def handle_message_deletion(sender, instance, **kwargs):
    """
    Handle message deletion.
    - Clean up related data (reactions, reports)
    """
    # Reactions and reports will be cascade deleted automatically
    # due to ForeignKey on_delete=CASCADE
    pass
