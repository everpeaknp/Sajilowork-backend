"""
Task Assignment models for tracking task execution and progress.
"""
import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class TaskAssignment(models.Model):
    """
    Track task assignments and progress.
    Created when a bid is accepted.
    """
    
    STATUS_CHOICES = [
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('approved', 'Approved'),
        ('revision_requested', 'Revision Requested'),
        ('disputed', 'Disputed'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Primary fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.OneToOneField(
        'tasks.Task',
        on_delete=models.CASCADE,
        related_name='assignment'
    )
    tasker = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='task_assignments'
    )
    bid = models.OneToOneField(
        'bids.Bid',
        on_delete=models.CASCADE,
        related_name='assignment'
    )
    
    # Progress tracking
    progress_percentage = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Progress percentage (0-100)"
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='assigned')
    
    # Dates
    assigned_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Completion details
    completion_proof = models.JSONField(
        default=list,
        blank=True,
        help_text="List of proof files/images"
    )
    completion_notes = models.TextField(blank=True)
    
    # Revision tracking
    revision_requested = models.BooleanField(default=False)
    revision_notes = models.TextField(blank=True)
    revision_count = models.PositiveIntegerField(default=0)
    max_revisions = models.PositiveIntegerField(default=3)
    
    # Metadata
    notes = models.TextField(blank=True, help_text="Internal notes")
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'task_assignments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tasker', 'status']),
            models.Index(fields=['task', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"Assignment: {self.task.title} → {self.tasker.get_full_name()}"
    
    def start_work(self):
        """Mark task as started."""
        if self.status == 'assigned':
            self.status = 'in_progress'
            self.started_at = timezone.now()
            self.save(update_fields=['status', 'started_at'])
            
            # Update task status
            self.task.status = 'in_progress'
            self.task.start_date = self.started_at
            self.task.save(update_fields=['status', 'start_date'])
    
    def update_progress(self, percentage: int, notes: str = ''):
        """Update progress percentage."""
        if not 0 <= percentage <= 100:
            raise ValueError("Progress must be between 0 and 100")
        
        self.progress_percentage = percentage
        if notes:
            self.notes = notes
        self.save(update_fields=['progress_percentage', 'notes', 'updated_at'])
    
    def mark_completed(self, proof: list, notes: str = ''):
        """Mark task as completed by tasker."""
        if self.status != 'in_progress':
            raise ValueError("Can only complete tasks that are in progress")
        
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.completion_proof = proof
        self.completion_notes = notes
        self.progress_percentage = 100
        self.save(update_fields=[
            'status', 'completed_at', 'completion_proof',
            'completion_notes', 'progress_percentage'
        ])
        
        # Update task status
        self.task.status = 'completed'
        self.task.completion_date = self.completed_at
        self.task.save(update_fields=['status', 'completion_date'])
    
    def approve_completion(self):
        """Approve task completion (by task owner)."""
        if self.status != 'completed':
            raise ValueError("Can only approve completed tasks")
        
        self.status = 'approved'
        self.approved_at = timezone.now()
        self.save(update_fields=['status', 'approved_at'])
        
        # Update task status to paid (ready for payment release)
        self.task.status = 'paid'
        self.task.save(update_fields=['status'])
    
    def request_revision(self, notes: str):
        """Request revision from tasker."""
        if self.status != 'completed':
            raise ValueError("Can only request revision for completed tasks")
        
        if self.revision_count >= self.max_revisions:
            raise ValueError(f"Maximum revisions ({self.max_revisions}) reached")
        
        self.status = 'revision_requested'
        self.revision_requested = True
        self.revision_notes = notes
        self.revision_count += 1
        self.save(update_fields=[
            'status', 'revision_requested', 'revision_notes', 'revision_count'
        ])
        
        # Update task status back to in_progress
        self.task.status = 'in_progress'
        self.task.save(update_fields=['status'])
    
    def resume_after_revision(self):
        """Resume work after revision request."""
        if self.status != 'revision_requested':
            raise ValueError("Can only resume revision-requested tasks")
        
        self.status = 'in_progress'
        self.revision_requested = False
        self.save(update_fields=['status', 'revision_requested'])
    
    @property
    def can_request_revision(self):
        """Check if revision can be requested."""
        return (
            self.status == 'completed' and
            self.revision_count < self.max_revisions
        )
    
    @property
    def time_elapsed(self):
        """Calculate time elapsed since assignment."""
        if self.started_at:
            end_time = self.completed_at or timezone.now()
            return end_time - self.started_at
        return None
    
    @property
    def is_overdue(self):
        """Check if assignment is overdue."""
        if self.task.due_date and self.status not in ['completed', 'approved', 'cancelled']:
            return timezone.now() > self.task.due_date
        return False


class ProgressUpdate(models.Model):
    """
    Track progress updates for task assignments.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(
        TaskAssignment,
        on_delete=models.CASCADE,
        related_name='progress_updates'
    )
    
    # Progress details
    progress_percentage = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    description = models.TextField()
    attachments = models.JSONField(default=list, blank=True)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'progress_updates'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['assignment', '-created_at']),
        ]
    
    def __str__(self):
        return f"Progress Update: {self.progress_percentage}% - {self.assignment}"


class CompletionProof(models.Model):
    """
    Store completion proof files/images.
    """
    
    FILE_TYPES = [
        ('image', 'Image'),
        ('document', 'Document'),
        ('video', 'Video'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(
        TaskAssignment,
        on_delete=models.CASCADE,
        related_name='proof_files'
    )
    
    # File details
    file_url = models.URLField()
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=20, choices=FILE_TYPES, default='other')
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    
    # Metadata
    description = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'completion_proofs'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"Proof: {self.file_name} - {self.assignment}"


class RevisionRequest(models.Model):
    """
    Track revision requests for task assignments.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(
        TaskAssignment,
        on_delete=models.CASCADE,
        related_name='revision_requests'
    )
    
    # Revision details
    requested_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='requested_revisions'
    )
    notes = models.TextField()
    attachments = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Response
    response_notes = models.TextField(blank=True)
    response_attachments = models.JSONField(default=list, blank=True)
    
    # Timestamps
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'revision_requests'
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['assignment', 'status']),
        ]
    
    def __str__(self):
        return f"Revision Request: {self.assignment} - {self.status}"
    
    def mark_completed(self, response_notes: str = '', attachments: list = None):
        """Mark revision as completed."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.response_notes = response_notes
        if attachments:
            self.response_attachments = attachments
        self.save(update_fields=[
            'status', 'completed_at', 'response_notes', 'response_attachments'
        ])
