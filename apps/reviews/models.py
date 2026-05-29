"""
Bidirectional review system: customer ↔ tasker after task completion and escrow release.
"""
import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.contrib.auth import get_user_model

from .constants import (
    REVIEWER_TYPE_CHOICES,
    REVIEWER_TYPE_CUSTOMER,
    REVIEWER_TYPE_TASKER,
    REVIEW_TYPE_OWNER_TO_PROVIDER,
    REVIEW_TYPE_PROVIDER_TO_OWNER,
    VISIBILITY_MODE_CHOICES,
    VISIBILITY_IMMEDIATE,
    DEFAULT_EDIT_WINDOW_MINUTES,
    DEFAULT_RATE_LIMIT_PER_HOUR,
)

User = get_user_model()


class ReviewPlatformSettings(models.Model):
    """Singleton-style platform settings for review behaviour (admin-configurable)."""

    visibility_mode = models.CharField(
        max_length=30,
        choices=VISIBILITY_MODE_CHOICES,
        default=VISIBILITY_IMMEDIATE,
    )
    edit_window_minutes = models.PositiveIntegerField(
        default=DEFAULT_EDIT_WINDOW_MINUTES,
        help_text='0 = immutable after submit; 15 = allow edits within 15 minutes.',
    )
    rate_limit_per_hour = models.PositiveIntegerField(default=DEFAULT_RATE_LIMIT_PER_HOUR)
    review_window_days = models.PositiveIntegerField(
        default=14,
        help_text='Days after escrow release that reviews remain open.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'review_platform_settings'
        verbose_name = 'Review platform settings'
        verbose_name_plural = 'Review platform settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Review(models.Model):
    """
    One review per (task, reviewer). Direction is enforced server-side:
    customer → tasker, tasker → customer.
    """

    REVIEW_TYPE_CHOICES = [
        (REVIEW_TYPE_OWNER_TO_PROVIDER, 'Owner to Provider'),
        (REVIEW_TYPE_PROVIDER_TO_OWNER, 'Provider to Owner'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    reviewer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reviews_given',
    )
    reviewee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reviews_received',
    )
    reviewer_type = models.CharField(max_length=20, choices=REVIEWER_TYPE_CHOICES)
    review_type = models.CharField(max_length=30, choices=REVIEW_TYPE_CHOICES)

    overall_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='Rating 1–5',
    )
    review_text = models.TextField(default='', blank=True)
    tags = models.JSONField(default=list, blank=True)

    # Optional detailed ratings (legacy / extended)
    communication_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True,
    )
    quality_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True,
    )
    speed_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True,
    )
    professionalism_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True,
    )
    clarity_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True,
    )
    payment_experience_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True,
    )

    would_recommend = models.BooleanField(default=True)
    would_work_again = models.BooleanField(default=True)

    is_public = models.BooleanField(default=False)
    visible_at = models.DateTimeField(null=True, blank=True)
    is_verified = models.BooleanField(default=True)
    is_finalized = models.BooleanField(default=False)
    finalized_at = models.DateTimeField(null=True, blank=True)

    response_text = models.TextField(blank=True)
    response_at = models.DateTimeField(null=True, blank=True)

    is_flagged = models.BooleanField(default=False)
    flag_reason = models.TextField(blank=True)
    is_approved = models.BooleanField(default=True)
    moderated_at = models.DateTimeField(null=True, blank=True)
    moderated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='moderated_reviews',
    )

    submitter_ip = models.GenericIPAddressField(null=True, blank=True)
    submitter_user_agent = models.CharField(max_length=512, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'reviews'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['task', 'reviewer'],
                name='unique_review_per_task_per_reviewer',
            ),
        ]
        indexes = [
            models.Index(fields=['task', 'reviewer_type']),
            models.Index(fields=['reviewer']),
            models.Index(fields=['reviewee', 'is_public', 'is_approved']),
            models.Index(fields=['overall_rating']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return (
            f"{self.reviewer_type} review by {self.reviewer_id} "
            f"for {self.reviewee_id} on task {self.task_id}"
        )

    @property
    def rating(self):
        return self.overall_rating

    @property
    def comment(self):
        return self.review_text

    @classmethod
    def reviewer_type_to_review_type(cls, reviewer_type: str) -> str:
        if reviewer_type == REVIEWER_TYPE_CUSTOMER:
            return REVIEW_TYPE_OWNER_TO_PROVIDER
        return REVIEW_TYPE_PROVIDER_TO_OWNER

    @classmethod
    def review_type_to_reviewer_type(cls, review_type: str) -> str:
        if review_type == REVIEW_TYPE_OWNER_TO_PROVIDER:
            return REVIEWER_TYPE_CUSTOMER
        return REVIEWER_TYPE_TASKER


class ReviewInvitation(models.Model):
    """Tracks review window per party after escrow release."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.CASCADE,
        related_name='review_invitations',
    )
    invitee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='review_invitations',
    )
    reviewer_type = models.CharField(max_length=20, choices=REVIEWER_TYPE_CHOICES)
    review_type = models.CharField(max_length=30, choices=Review.REVIEW_TYPE_CHOICES)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    sent_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)

    review = models.OneToOneField(
        Review,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invitation',
    )

    class Meta:
        db_table = 'review_invitations'
        ordering = ['-sent_at']
        constraints = [
            models.UniqueConstraint(
                fields=['task', 'invitee'],
                name='unique_review_invitation_per_task_per_user',
            ),
        ]
        indexes = [
            models.Index(fields=['invitee', 'status']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"Review invitation for {self.invitee_id} on task {self.task_id}"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at and self.status == 'pending'


class ReviewHelpful(models.Model):
    """Helpful votes on published reviews."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='helpful_votes',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='review_helpful_votes',
    )
    is_helpful = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'review_helpful'
        constraints = [
            models.UniqueConstraint(
                fields=['review', 'user'],
                name='unique_helpful_vote_per_user',
            ),
        ]
        indexes = [
            models.Index(fields=['review', 'is_helpful']),
        ]


class ReviewReport(models.Model):
    """Report inappropriate reviews for admin moderation."""

    REASON_CHOICES = [
        ('spam', 'Spam'),
        ('offensive', 'Offensive Language'),
        ('fake', 'Fake Review'),
        ('irrelevant', 'Irrelevant Content'),
        ('personal_info', 'Contains Personal Information'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='reports',
    )
    reporter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='review_reports',
    )
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    description = models.TextField()

    is_resolved = models.BooleanField(default=False)
    resolution_notes = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_review_reports',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'review_reports'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['review', 'reporter'],
                name='unique_review_report_per_user',
            ),
        ]
        indexes = [
            models.Index(fields=['is_resolved', 'created_at']),
        ]
