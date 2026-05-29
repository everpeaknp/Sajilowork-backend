"""
Signal handlers for Tasks app.
"""
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils.text import slugify
from .models import Task, TaskBookmark


@receiver(pre_save, sender=Task)
def generate_task_slug(sender, instance, **kwargs):
    """Generate unique slug for task if not provided."""
    if not instance.slug:
        slug = slugify(instance.title)
        counter = 1
        original_slug = slug
        
        while Task.objects.filter(slug=slug).exclude(pk=instance.pk).exists():
            slug = f"{original_slug}-{counter}"
            counter += 1
        
        instance.slug = slug


@receiver(post_save, sender=Task)
def task_created_notification(sender, instance, created, **kwargs):
    """Send notifications when task is created or status changes."""
    if created:
        # TODO: Notify nearby taskers about new task
        # TODO: Send email to task owner confirming creation
        pass
    # Note: Status change tracking removed - requires django-model-utils FieldTracker
    # TODO: Implement status change notifications when needed


@receiver(post_save, sender=Task)
def update_user_stats(sender, instance, **kwargs):
    """Update user statistics when task status changes."""
    if instance.status == 'completed':
        # Update owner's tasks_posted count
        owner = instance.owner
        owner.tasks_posted = Task.objects.filter(
            owner=owner,
            status='completed'
        ).count()
        owner.save(update_fields=['tasks_posted'])
        
        # Update tasker's tasks_completed count
        if instance.assigned_tasker:
            tasker = instance.assigned_tasker
            tasker.tasks_completed = Task.objects.filter(
                assigned_tasker=tasker,
                status='completed'
            ).count()
            tasker.save(update_fields=['tasks_completed'])


@receiver(post_save, sender=TaskBookmark)
def increment_bookmark_count(sender, instance, created, **kwargs):
    """Increment bookmark count when bookmark is created."""
    if created:
        task = instance.task
        task.bookmarks_count += 1
        task.save(update_fields=['bookmarks_count'])


@receiver(post_delete, sender=TaskBookmark)
def decrement_bookmark_count(sender, instance, **kwargs):
    """Decrement bookmark count when bookmark is deleted."""
    try:
        task = instance.task
        if task and task.pk:
            task.bookmarks_count = max(0, task.bookmarks_count - 1)
            task.save(update_fields=['bookmarks_count'])
    except (Task.DoesNotExist, AttributeError, ValueError):
        # Task was already deleted (cascade delete), nothing to update
        pass
