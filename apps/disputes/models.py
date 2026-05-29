"""
Dispute models for conflict resolution.
"""
import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Dispute(models.Model):
    """
    Dispute raised by customer or provider for conflict resolution.
    """
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('under_review', 'Under Review'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
        ('escalated', 'Escalated'),
    ]
    
    DISPUTE_TYPE_CHOICES = [
        ('quality', 'Quality Issue'),
        ('incomplete', 'Incomplete Work'),
        ('deadline', 'Deadline Missed'),
        ('payment', 'Payment Issue'),
        ('communication', 'Communication Problem'),
        ('other', 'Other'),
    ]
    
    RESOLUTION_CHOICES = [
        ('refund_full', 'Full Refund'),
        ('refund_partial', 'Partial Refund'),
        ('release_payment', 'Release Payment'),
        ('revision_required', 'Revision Required'),
        ('no_action', 'No Action'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.CASCADE,
        related_name='disputes'
    )
    raised_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='disputes_raised'
    )
    against = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='disputes_against'
    )
    
    # Dispute details
    dispute_type = models.CharField(max_length=30, choices=DISPUTE_TYPE_CHOICES)
    title = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    
    # Resolution
    resolution = models.CharField(
        max_length=30,
        choices=RESOLUTION_CHOICES,
        blank=True,
        null=True
    )
    resolution_notes = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='disputes_resolved'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Admin assignment
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_disputes',
        limit_choices_to={'role': 'admin'}
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'disputes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['task']),
            models.Index(fields=['raised_by']),
        ]
    
    def __str__(self):
        return f"Dispute #{self.id} - {self.task.title}"


class DisputeEvidence(models.Model):
    """
    Evidence submitted for disputes (files, screenshots, messages).
    """
    
    EVIDENCE_TYPES = [
        ('image', 'Image'),
        ('document', 'Document'),
        ('video', 'Video'),
        ('message', 'Message Screenshot'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dispute = models.ForeignKey(
        Dispute,
        on_delete=models.CASCADE,
        related_name='evidence'
    )
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )
    evidence_type = models.CharField(max_length=20, choices=EVIDENCE_TYPES)
    file_url = models.URLField()
    file_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'dispute_evidence'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"Evidence for Dispute #{self.dispute.id}"


class DisputeMessage(models.Model):
    """
    Messages exchanged during dispute resolution.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dispute = models.ForeignKey(
        Dispute,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )
    message = models.TextField()
    is_admin_message = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'dispute_messages'
        ordering = ['created_at']
    
    def __str__(self):
        return f"Message in Dispute #{self.dispute.id}"
