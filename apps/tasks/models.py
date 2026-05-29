"""
Task models for the Airtasker marketplace.
"""
import uuid
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.utils.text import slugify
from django.contrib.auth import get_user_model

User = get_user_model()


class Category(models.Model):
    """Task categories."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Icon class or emoji")
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories'
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'Categories'
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name


class Task(models.Model):
    """Main Task model."""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('assigned', 'Assigned'),
        ('funded', 'Funded'),
        ('in_progress', 'In Progress'),
        ('pending_approval', 'Pending Approval'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('disputed', 'Disputed'),
    ]
    
    WORK_TYPE_CHOICES = [
        ('remote', 'Remote'),
        ('in_person', 'In Person'),
        ('flexible', 'Flexible'),
    ]
    
    URGENCY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    # Primary fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField()
    
    # Relationships
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='posted_tasks'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name='tasks'
    )
    assigned_tasker = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tasks'
    )
    
    # Task details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    work_type = models.CharField(max_length=20, choices=WORK_TYPE_CHOICES, default='flexible')
    urgency = models.CharField(max_length=20, choices=URGENCY_CHOICES, default='medium')
    
    # Budget
    budget_type = models.CharField(
        max_length=20,
        choices=[('fixed', 'Fixed Price'), ('hourly', 'Hourly Rate')],
        default='fixed'
    )
    budget_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    budget_currency = models.CharField(max_length=3, default='NPR')
    
    # Location
    location_type = models.CharField(
        max_length=20,
        choices=[('remote', 'Remote'), ('physical', 'Physical Location')],
        default='physical'
    )
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Dates
    due_date = models.DateTimeField(null=True, blank=True)
    start_date = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completion_date = models.DateTimeField(null=True, blank=True)
    completion_requested_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    tasker_marked_complete_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the assigned tasker confirmed work is complete',
    )
    owner_marked_complete_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the poster confirmed work is complete',
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    cancelled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks_cancelled',
    )

    # Visibility and features
    is_public = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    allow_bids = models.BooleanField(default=True)
    auto_accept_bid = models.BooleanField(default=False)
    
    # Statistics
    views_count = models.PositiveIntegerField(default=0)
    bids_count = models.PositiveIntegerField(default=0)
    bookmarks_count = models.PositiveIntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    tags = models.JSONField(default=list, blank=True)
    requirements = models.JSONField(default=list, blank=True)
    
    class Meta:
        db_table = 'tasks'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'is_public']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['owner']),
            models.Index(fields=['assigned_tasker']),
            models.Index(fields=['city', 'country']),
            models.Index(fields=['created_at']),
            models.Index(fields=['due_date']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        """Override save to auto-generate slug from title."""
        if not self.slug:
            # Generate slug from title
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            
            # Ensure unique slug
            while Task.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            self.slug = slug
        
        super().save(*args, **kwargs)
    
    @property
    def is_open(self):
        """Check if task is open for bids."""
        return self.status == 'open' and self.allow_bids
    
    @property
    def is_completed(self):
        """Check if task is completed."""
        return self.status == 'completed'
    
    @property
    def is_overdue(self):
        """Check if task is overdue."""
        if self.due_date and self.status not in ['completed', 'cancelled']:
            return timezone.now() > self.due_date
        return False
    
    @property
    def full_address(self):
        """Return formatted full address."""
        parts = [self.address, self.city, self.state, self.postal_code, self.country]
        return ', '.join(filter(None, parts))
    
    def publish(self):
        """Publish the task."""
        if self.status == 'draft':
            self.status = 'open'
            self.published_at = timezone.now()
            self.save(update_fields=['status', 'published_at'])
    
    def assign_to_tasker(self, tasker):
        """Assign task to a tasker."""
        self.assigned_tasker = tasker
        self.status = 'assigned'
        self.save(update_fields=['assigned_tasker', 'status'])
    
    def mark_in_progress(self):
        """Mark task as in progress."""
        if self.status == 'assigned':
            self.status = 'in_progress'
            self.start_date = timezone.now()
            self.save(update_fields=['status', 'start_date'])
    
    def mark_completed(self):
        """Mark task as completed."""
        if self.status == 'in_progress':
            self.status = 'completed'
            self.completion_date = timezone.now()
            self.save(update_fields=['status', 'completion_date'])
    
    def cancel(self, user=None, cancellation_reason=''):
        """Cancel the task and record who cancelled it."""
        if self.status not in ['completed', 'cancelled']:
            self.status = 'cancelled'
            self.cancelled_at = timezone.now()
            if user is not None:
                self.cancelled_by = user
            if cancellation_reason:
                self.cancellation_reason = cancellation_reason
            update_fields = ['status', 'cancelled_at']
            if user is not None:
                update_fields.append('cancelled_by')
            if cancellation_reason:
                update_fields.append('cancellation_reason')
            self.save(update_fields=update_fields)


class TaskAttachment(models.Model):
    """Attachments for tasks."""
    
    FILE_TYPES = [
        ('image', 'Image'),
        ('document', 'Document'),
        ('video', 'Video'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='attachments')
    file_url = models.URLField()
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=20, choices=FILE_TYPES, default='other')
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'task_attachments'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.task.title} - {self.file_name}"


class TaskBookmark(models.Model):
    """User bookmarks for tasks."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookmarked_tasks')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='bookmarks')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'task_bookmarks'
        unique_together = ['user', 'task']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.task.title}"


class TaskView(models.Model):
    """Track task views."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='views')
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='viewed_tasks'
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    viewed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'task_views'
        ordering = ['-viewed_at']
        indexes = [
            models.Index(fields=['task', 'viewed_at']),
        ]
    
    def __str__(self):
        return f"{self.task.title} - {self.viewed_at}"


class TaskQuestion(models.Model):
    """Questions asked about tasks."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='questions')
    asked_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='asked_questions')
    question = models.TextField()
    answer = models.TextField(blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'task_questions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Q: {self.question[:50]}"
    
    @property
    def is_answered(self):
        """Check if question is answered."""
        return bool(self.answer)


class TaskReport(models.Model):
    """Reports for inappropriate tasks."""
    
    REASON_CHOICES = [
        ('spam', 'Spam'),
        ('inappropriate', 'Inappropriate Content'),
        ('fraud', 'Fraud/Scam'),
        ('duplicate', 'Duplicate'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('reviewed', 'Reviewed'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='reports')
    reported_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task_reports')
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_task_reports'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'task_reports'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Report: {self.task.title} - {self.get_reason_display()}"



class TaskActivity(models.Model):
    """
    Activity timeline for tasks.
    Tracks all important events in the task lifecycle.
    """
    
    ACTIVITY_TYPES = [
        ('created', 'Task Created'),
        ('published', 'Task Published'),
        ('bid_received', 'Bid Received'),
        ('bid_accepted', 'Bid Accepted'),
        ('bid_rejected', 'Bid Rejected'),
        ('assigned', 'Task Assigned'),
        ('started', 'Task Started'),
        ('progress_updated', 'Progress Updated'),
        ('completion_requested', 'Completion Requested'),
        ('revision_requested', 'Revision Requested'),
        ('completed', 'Task Completed'),
        ('approved', 'Task Approved'),
        ('payment_released', 'Payment Released'),
        ('reviewed', 'Review Submitted'),
        ('cancelled', 'Task Cancelled'),
        ('disputed', 'Dispute Raised'),
        ('message_sent', 'Message Sent'),
        ('attachment_uploaded', 'Attachment Uploaded'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='activities'
    )
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES)
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='task_activities'
    )
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'task_activities'
        verbose_name_plural = 'Task Activities'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['task', '-created_at']),
            models.Index(fields=['activity_type']),
        ]
    
    def __str__(self):
        return f"{self.task.title} - {self.get_activity_type_display()}"
