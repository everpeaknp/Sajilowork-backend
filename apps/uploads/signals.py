"""
Uploads Signals
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Upload, UploadQuota


@receiver(post_save, sender=Upload)
def process_upload_on_create(sender, instance, created, **kwargs):
    """Process upload after creation"""
    if created and instance.status == 'pending':
        # TODO: Trigger async processing with Celery
        # from .tasks import process_upload_task
        # process_upload_task.delay(instance.id)
        pass


@receiver(post_delete, sender=Upload)
def delete_file_on_delete(sender, instance, **kwargs):
    """Delete file from storage when Upload is deleted"""
    if instance.file:
        instance.file.delete(save=False)
