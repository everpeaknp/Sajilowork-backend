"""
Analytics models for tracking events and generating insights.
"""
import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

User = get_user_model()


class Event(models.Model):
    """
    Track user events and actions across the platform.
    """
    
    EVENT_CATEGORIES = [
        ('user', 'User'),
        ('task', 'Task'),
        ('bid', 'Bid'),
        ('payment', 'Payment'),
        ('chat', 'Chat'),
        ('review', 'Review'),
        ('search', 'Search'),
        ('notification', 'Notification'),
        ('system', 'System'),
    ]
    
    EVENT_TYPES = [
        # User events
        ('user_registered', 'User Registered'),
        ('user_login', 'User Login'),
        ('user_logout', 'User Logout'),
        ('profile_updated', 'Profile Updated'),
        ('profile_viewed', 'Profile Viewed'),
        
        # Task events
        ('task_created', 'Task Created'),
        ('task_published', 'Task Published'),
        ('task_viewed', 'Task Viewed'),
        ('task_bookmarked', 'Task Bookmarked'),
        ('task_completed', 'Task Completed'),
        ('task_cancelled', 'Task Cancelled'),
        
        # Bid events
        ('bid_submitted', 'Bid Submitted'),
        ('bid_accepted', 'Bid Accepted'),
        ('bid_rejected', 'Bid Rejected'),
        ('bid_withdrawn', 'Bid Withdrawn'),
        
        # Payment events
        ('payment_initiated', 'Payment Initiated'),
        ('payment_completed', 'Payment Completed'),
        ('payment_failed', 'Payment Failed'),
        ('refund_requested', 'Refund Requested'),
        ('payout_completed', 'Payout Completed'),
        
        # Chat events
        ('message_sent', 'Message Sent'),
        ('conversation_started', 'Conversation Started'),
        
        # Review events
        ('review_submitted', 'Review Submitted'),
        ('review_responded', 'Review Responded'),
        
        # Search events
        ('search_performed', 'Search Performed'),
        ('filter_applied', 'Filter Applied'),
        
        # Notification events
        ('notification_sent', 'Notification Sent'),
        ('notification_read', 'Notification Read'),
        
        # System events
        ('error_occurred', 'Error Occurred'),
        ('api_called', 'API Called'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='events')
    session_id = models.CharField(max_length=255, blank=True, help_text="Session identifier")
    
    # Event details
    category = models.CharField(max_length=50, choices=EVENT_CATEGORIES)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    event_name = models.CharField(max_length=255, help_text="Human-readable event name")
    
    # Generic relation to any model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.UUIDField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Event metadata
    properties = models.JSONField(default=dict, blank=True, help_text="Additional event properties")
    
    # Request metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    referrer = models.URLField(blank=True, null=True)
    
    # Location
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    
    # Device info
    device_type = models.CharField(max_length=50, blank=True, help_text="mobile, tablet, desktop")
    os = models.CharField(max_length=50, blank=True)
    browser = models.CharField(max_length=50, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'analytics_events'
        verbose_name = 'Event'
        verbose_name_plural = 'Events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['category', 'event_type']),
            models.Index(fields=['session_id']),
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.event_name} - {self.created_at}"


class Metric(models.Model):
    """
    Store aggregated metrics for reporting and dashboards.
    """
    
    METRIC_TYPES = [
        ('counter', 'Counter'),
        ('gauge', 'Gauge'),
        ('histogram', 'Histogram'),
        ('rate', 'Rate'),
    ]
    
    AGGREGATION_PERIODS = [
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Metric identification
    name = models.CharField(max_length=255, db_index=True)
    metric_type = models.CharField(max_length=20, choices=METRIC_TYPES)
    category = models.CharField(max_length=50, blank=True)
    
    # Metric value
    value = models.DecimalField(max_digits=20, decimal_places=4)
    
    # Aggregation
    aggregation_period = models.CharField(max_length=20, choices=AGGREGATION_PERIODS)
    period_start = models.DateTimeField(db_index=True)
    period_end = models.DateTimeField()
    
    # Dimensions (for filtering/grouping)
    dimensions = models.JSONField(default=dict, blank=True, help_text="Metric dimensions")
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'analytics_metrics'
        verbose_name = 'Metric'
        verbose_name_plural = 'Metrics'
        ordering = ['-period_start']
        unique_together = ['name', 'aggregation_period', 'period_start', 'dimensions']
        indexes = [
            models.Index(fields=['name', '-period_start']),
            models.Index(fields=['category', '-period_start']),
            models.Index(fields=['aggregation_period', '-period_start']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.period_start}"


class Funnel(models.Model):
    """
    Track conversion funnels (e.g., task creation, bid acceptance).
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Funnel identification
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    
    # Funnel steps (ordered list)
    steps = models.JSONField(
        default=list,
        help_text="List of step names in order"
    )
    
    # Configuration
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'analytics_funnels'
        verbose_name = 'Funnel'
        verbose_name_plural = 'Funnels'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class FunnelStep(models.Model):
    """
    Track user progress through funnel steps.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    funnel = models.ForeignKey(Funnel, on_delete=models.CASCADE, related_name='funnel_steps')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='funnel_steps')
    session_id = models.CharField(max_length=255, blank=True)
    
    # Step details
    step_name = models.CharField(max_length=255)
    step_index = models.PositiveIntegerField()
    
    # Completion
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    properties = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'analytics_funnel_steps'
        verbose_name = 'Funnel Step'
        verbose_name_plural = 'Funnel Steps'
        ordering = ['funnel', 'step_index', '-created_at']
        indexes = [
            models.Index(fields=['funnel', 'user']),
            models.Index(fields=['session_id']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.funnel.name} - {self.step_name}"


class Cohort(models.Model):
    """
    Define user cohorts for analysis.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Cohort identification
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    
    # Cohort definition
    criteria = models.JSONField(
        default=dict,
        help_text="Criteria for cohort membership"
    )
    
    # Members
    users = models.ManyToManyField(User, related_name='cohorts', blank=True)
    
    # Configuration
    is_active = models.BooleanField(default=True)
    auto_update = models.BooleanField(
        default=False,
        help_text="Automatically update cohort membership"
    )
    
    # Statistics
    member_count = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'analytics_cohorts'
        verbose_name = 'Cohort'
        verbose_name_plural = 'Cohorts'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.member_count} members)"
    
    def update_members(self):
        """Update cohort membership based on criteria."""
        # TODO: Implement cohort criteria evaluation
        self.member_count = self.users.count()
        self.last_updated = timezone.now()
        self.save(update_fields=['member_count', 'last_updated'])


class Report(models.Model):
    """
    Scheduled analytics reports.
    """
    
    REPORT_TYPES = [
        ('user_activity', 'User Activity'),
        ('task_performance', 'Task Performance'),
        ('revenue', 'Revenue'),
        ('engagement', 'Engagement'),
        ('retention', 'Retention'),
        ('custom', 'Custom'),
    ]
    
    FREQUENCIES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Report identification
    name = models.CharField(max_length=255)
    report_type = models.CharField(max_length=50, choices=REPORT_TYPES)
    description = models.TextField(blank=True)
    
    # Configuration
    frequency = models.CharField(max_length=20, choices=FREQUENCIES)
    recipients = models.JSONField(
        default=list,
        help_text="List of email addresses"
    )
    
    # Report parameters
    parameters = models.JSONField(default=dict, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'analytics_reports'
        verbose_name = 'Report'
        verbose_name_plural = 'Reports'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()})"
