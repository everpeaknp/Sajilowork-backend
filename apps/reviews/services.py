"""
Bidirectional review service — server-side role detection, eligibility, visibility, trust score.
"""
from datetime import timedelta
from decimal import Decimal
import logging

from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone

from django.apps import apps as django_apps

from apps.payments.models import Payment
from apps.tasks.models import Task
from apps.users.models import User

from .constants import (
    CUSTOMER_TO_TASKER_TAGS,
    REVIEWER_TYPE_CUSTOMER,
    REVIEWER_TYPE_TASKER,
    TASKER_TO_CUSTOMER_TAGS,
    VISIBILITY_BOTH_SUBMITTED,
    VISIBILITY_DELAY_24H,
    VISIBILITY_IMMEDIATE,
    DEFAULT_REVIEW_WINDOW_DAYS,
)
from .models import Review, ReviewInvitation, ReviewPlatformSettings

logger = logging.getLogger(__name__)


class ReviewEligibilityError(ValidationError):
    """Raised when a user cannot submit a review for a task."""


class ReviewService:
    """Enforces bidirectional review rules and updates reputation."""

    @staticmethod
    def get_settings() -> ReviewPlatformSettings:
        return ReviewPlatformSettings.get_solo()

    @staticmethod
    def resolve_reviewer_type(task: Task, reviewer: User) -> str:
        """Detect CUSTOMER vs TASKER from task participants only."""
        if reviewer.id == task.owner_id:
            return REVIEWER_TYPE_CUSTOMER
        if task.assigned_tasker_id and reviewer.id == task.assigned_tasker_id:
            return REVIEWER_TYPE_TASKER
        raise PermissionDenied('You are not a participant on this task.')

    @staticmethod
    def resolve_reviewee(task: Task, reviewer_type: str) -> User:
        if reviewer_type == REVIEWER_TYPE_CUSTOMER:
            if not task.assigned_tasker_id:
                raise ReviewEligibilityError('Task has no assigned tasker to review.')
            return task.assigned_tasker
        return task.owner

    @staticmethod
    def _payment_released_for_task(task: Task) -> bool:
        task_ct = ContentType.objects.get_for_model(Task)
        return Payment.objects.filter(
            content_type=task_ct,
            object_id=task.id,
            status='released',
        ).exists()

    @staticmethod
    def _disputes_allow_reviews(task: Task) -> bool:
        if task.status == 'disputed':
            return False
        if not django_apps.is_installed('apps.disputes'):
            return True
        Dispute = django_apps.get_model('disputes', 'Dispute')
        disputes = Dispute.objects.filter(task=task)
        if not disputes.exists():
            return True
        return not disputes.exclude(status='closed').exists()

    @staticmethod
    def assert_can_review(task: Task, reviewer: User) -> str:
        """
        Validate all gates. Returns reviewer_type on success.
        """
        if task.status != 'completed':
            raise ReviewEligibilityError('Reviews are only allowed after the task is completed.')

        if not task.assigned_tasker_id:
            raise ReviewEligibilityError('Task must have an assigned tasker before reviews.')

        reviewer_type = ReviewService.resolve_reviewer_type(task, reviewer)
        reviewee = ReviewService.resolve_reviewee(task, reviewer_type)

        if reviewer.id == reviewee.id:
            raise ReviewEligibilityError('You cannot review yourself.')

        # NOTE: This project allows reviews immediately after task completion.
        # Escrow / dispute gating can be re-enabled by adding additional checks here.

        if Review.objects.filter(task=task, reviewer=reviewer).exists():
            raise ReviewEligibilityError('You have already submitted a review for this task.')

        settings = ReviewService.get_settings()
        invitation = ReviewInvitation.objects.filter(
            task=task,
            invitee=reviewer,
            status='pending',
        ).first()
        if invitation and invitation.is_expired:
            raise ReviewEligibilityError('The review window for this task has expired.')

        ReviewService._check_rate_limit(reviewer, settings.rate_limit_per_hour)

        return reviewer_type

    @staticmethod
    def _check_rate_limit(user: User, limit_per_hour: int) -> None:
        key = f'review_submit:{user.id}'
        count = cache.get(key, 0)
        if count >= limit_per_hour:
            raise ReviewEligibilityError(
                'Too many reviews submitted recently. Please try again later.'
            )

    @staticmethod
    def _increment_rate_limit(user: User) -> None:
        key = f'review_submit:{user.id}'
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, 3600)

    @staticmethod
    def validate_tags(reviewer_type: str, tags: list) -> list:
        if not tags:
            return []
        allowed = (
            CUSTOMER_TO_TASKER_TAGS
            if reviewer_type == REVIEWER_TYPE_CUSTOMER
            else TASKER_TO_CUSTOMER_TAGS
        )
        normalized = []
        for tag in tags:
            if not isinstance(tag, str):
                continue
            key = tag.strip().lower().replace(' ', '_')
            if key in allowed:
                normalized.append(key)
        return normalized

    @staticmethod
    def _compute_visibility(review: Review, settings: ReviewPlatformSettings) -> None:
        now = timezone.now()
        if settings.visibility_mode == VISIBILITY_IMMEDIATE:
            review.is_public = True
            review.visible_at = now
        elif settings.visibility_mode == VISIBILITY_DELAY_24H:
            review.is_public = False
            review.visible_at = now + timedelta(hours=24)
        elif settings.visibility_mode == VISIBILITY_BOTH_SUBMITTED:
            review.is_public = False
            review.visible_at = None
            task_reviews = Review.objects.filter(task=review.task, is_approved=True)
            has_customer = task_reviews.filter(reviewer_type=REVIEWER_TYPE_CUSTOMER).exists()
            has_tasker = task_reviews.filter(reviewer_type=REVIEWER_TYPE_TASKER).exists()
            if has_customer and has_tasker:
                review.is_public = True
                review.visible_at = now

    @staticmethod
    def refresh_task_review_visibility(task: Task) -> None:
        """Re-evaluate visibility for all reviews on a task (e.g. after second review)."""
        settings = ReviewService.get_settings()
        if settings.visibility_mode != VISIBILITY_BOTH_SUBMITTED:
            return
        reviews = list(Review.objects.filter(task=task, is_approved=True))
        types = {r.reviewer_type for r in reviews}
        if REVIEWER_TYPE_CUSTOMER not in types or REVIEWER_TYPE_TASKER not in types:
            return
        now = timezone.now()
        Review.objects.filter(task=task, is_approved=True).update(
            is_public=True,
            visible_at=now,
        )

    @staticmethod
    @transaction.atomic
    def create_review(
        *,
        task_id,
        reviewer: User,
        rating: int,
        comment: str = '',
        tags: list | None = None,
        submitter_ip: str | None = None,
        submitter_user_agent: str = '',
        detailed_ratings: dict | None = None,
    ) -> Review:
        task = Task.objects.select_related('owner', 'assigned_tasker').get(id=task_id)
        reviewer_type = ReviewService.assert_can_review(task, reviewer)
        reviewee = ReviewService.resolve_reviewee(task, reviewer_type)

        if not 1 <= rating <= 5:
            raise ValidationError('Rating must be between 1 and 5.')

        settings = ReviewService.get_settings()
        review_type = Review.reviewer_type_to_review_type(reviewer_type)
        now = timezone.now()
        edit_window = settings.edit_window_minutes

        review = Review(
            task=task,
            reviewer=reviewer,
            reviewee=reviewee,
            reviewer_type=reviewer_type,
            review_type=review_type,
            overall_rating=rating,
            review_text=(comment or '').strip(),
            tags=ReviewService.validate_tags(reviewer_type, tags or []),
            submitter_ip=submitter_ip,
            submitter_user_agent=(submitter_user_agent or '')[:512],
            is_verified=True,
            is_approved=True,
            is_finalized=edit_window == 0,
            finalized_at=now if edit_window == 0 else None,
        )

        if detailed_ratings:
            review.communication_rating = detailed_ratings.get('communication')
            review.quality_rating = detailed_ratings.get('quality')
            review.professionalism_rating = detailed_ratings.get('professionalism')
            review.speed_rating = detailed_ratings.get('timeliness') or detailed_ratings.get('speed')
            review.clarity_rating = detailed_ratings.get('clarity')
            review.payment_experience_rating = detailed_ratings.get('payment_experience')

        ReviewService._compute_visibility(review, settings)
        review.save()

        ReviewService._increment_rate_limit(reviewer)
        ReviewService._complete_invitation(task, reviewer, review)
        ReviewService.refresh_task_review_visibility(task)
        ReviewService.update_user_profile_stats(reviewee)
        ReviewService.check_mutual_review_complete(task)

        try:
            from apps.notifications.services import NotificationService

            NotificationService.send_notification(
                user=reviewee,
                notification_type='review_received',
                title='New review received',
                message=f'{reviewer.get_full_name()} left you a {rating}-star review.',
                related_object=review,
                data={'review_id': str(review.id), 'task_id': str(task.id), 'rating': rating},
            )
        except Exception as exc:
            logger.warning('Review notification failed: %s', exc)

        logger.info(
            'Review %s created: %s → %s on task %s',
            review.id,
            reviewer_type,
            reviewee.id,
            task.id,
        )
        return review

    @staticmethod
    def _complete_invitation(task: Task, reviewer: User, review: Review) -> None:
        invitation = ReviewInvitation.objects.filter(
            task=task,
            invitee=reviewer,
            status='pending',
        ).first()
        if invitation:
            invitation.status = 'completed'
            invitation.completed_at = timezone.now()
            invitation.review = review
            invitation.save(update_fields=['status', 'completed_at', 'review'])

    @staticmethod
    @transaction.atomic
    def send_review_invitations(task: Task) -> list[ReviewInvitation]:
        """Open review window after escrow release (called from task completion workflow)."""
        if not task.assigned_tasker_id:
            return []

        settings = ReviewService.get_settings()
        expires_at = timezone.now() + timedelta(days=settings.review_window_days)
        created = []

        for invitee, reviewer_type in (
            (task.owner, REVIEWER_TYPE_CUSTOMER),
            (task.assigned_tasker, REVIEWER_TYPE_TASKER),
        ):
            review_type = Review.reviewer_type_to_review_type(reviewer_type)
            invitation, was_created = ReviewInvitation.objects.get_or_create(
                task=task,
                invitee=invitee,
                defaults={
                    'reviewer_type': reviewer_type,
                    'review_type': review_type,
                    'expires_at': expires_at,
                    'status': 'pending',
                },
            )
            if not was_created and invitation.status == 'pending':
                invitation.expires_at = expires_at
                invitation.save(update_fields=['expires_at'])
            if was_created:
                created.append(invitation)

        logger.info('Review invitations sent for task %s (%s new)', task.id, len(created))
        return created

    @staticmethod
    def public_reviews_queryset():
        now = timezone.now()
        return Review.objects.filter(
            is_approved=True,
            is_flagged=False,
        ).filter(
            Q(is_public=True)
            | Q(visible_at__lte=now, visible_at__isnull=False)
        )

    @staticmethod
    def get_reviews_received(user: User, limit: int | None = None):
        qs = (
            ReviewService.public_reviews_queryset()
            .filter(reviewee=user)
            .select_related('reviewer', 'task')
            .order_by('-created_at')
        )
        if limit:
            return qs[:limit]
        return qs

    @staticmethod
    def update_user_profile_stats(user: User) -> None:
        reviews = ReviewService.public_reviews_queryset().filter(reviewee=user)
        stats = reviews.aggregate(
            avg_rating=Avg('overall_rating'),
            total=Count('id'),
        )
        user.average_rating = round(stats['avg_rating'] or 0, 2)
        user.total_reviews = stats['total'] or 0

        if hasattr(user, 'trust_score'):
            user.trust_score = ReviewService.calculate_trust_score(user)

        user.save(update_fields=[
            f for f in ['average_rating', 'total_reviews', 'trust_score']
            if hasattr(user, f)
        ])

    @staticmethod
    def calculate_trust_score(user: User) -> Decimal:
        """
        Trust score (0–100):
        - Average rating 40%
        - Completion rate 30%
        - Cancellation rate 20% (inverted)
        - Dispute history 10% (inverted)
        """
        reviews = ReviewService.public_reviews_queryset().filter(reviewee=user)
        avg = reviews.aggregate(a=Avg('overall_rating'))['a']
        rating_component = (Decimal(str(avg or 0)) / Decimal('5')) * Decimal('40')

        completion = Decimal(str(getattr(user, 'completion_rate', 0) or 0))
        completion_component = (completion / Decimal('100')) * Decimal('30')

        posted = getattr(user, 'tasks_posted', 0) or 0
        completed = getattr(user, 'tasks_completed', 0) or 0
        if posted > 0:
            cancel_rate = max(
                Decimal('0'),
                Decimal('100') - (Decimal(completed) / Decimal(posted) * Decimal('100')),
            )
        else:
            cancel_rate = Decimal('0')
        cancellation_component = max(
            Decimal('0'),
            (Decimal('100') - cancel_rate) / Decimal('100') * Decimal('20'),
        )

        dispute_count = 0
        if django_apps.is_installed('apps.disputes'):
            Dispute = django_apps.get_model('disputes', 'Dispute')
            dispute_count = Dispute.objects.filter(
                Q(raised_by=user) | Q(against=user),
            ).count()
        dispute_penalty = min(Decimal('10'), Decimal(dispute_count) * Decimal('2'))
        dispute_component = Decimal('10') - dispute_penalty

        total = (
            rating_component
            + completion_component
            + cancellation_component
            + dispute_component
        )
        return max(Decimal('0'), min(Decimal('100'), total.quantize(Decimal('0.01'))))

    @staticmethod
    def check_mutual_review_complete(task: Task) -> None:
        has_customer = Review.objects.filter(
            task=task,
            reviewer_type=REVIEWER_TYPE_CUSTOMER,
        ).exists()
        has_tasker = Review.objects.filter(
            task=task,
            reviewer_type=REVIEWER_TYPE_TASKER,
        ).exists()
        if not (has_customer and has_tasker):
            return
        try:
            from apps.notifications.services import NotificationService

            for user in (task.owner, task.assigned_tasker):
                if user:
                    NotificationService.send_notification(
                        user=user,
                        notification_type='mutual_review_complete',
                        title='Mutual reviews complete',
                        message=f'Both parties have reviewed task "{task.title}".',
                        related_object=task,
                        data={'task_id': str(task.id)},
                    )
        except Exception as exc:
            logger.warning('Mutual review notification failed: %s', exc)

    @staticmethod
    def get_review_statistics(user: User) -> dict:
        reviews = ReviewService.public_reviews_queryset().filter(reviewee=user)
        if not reviews.exists():
            return {
                'total_reviews': 0,
                'average_rating': None,
                'rating_distribution': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                'as_tasker_reviews': 0,
                'as_customer_reviews': 0,
                'trust_score': ReviewService.calculate_trust_score(user),
            }

        rating_dist = {i: reviews.filter(overall_rating=i).count() for i in range(1, 6)}
        return {
            'total_reviews': reviews.count(),
            'average_rating': float(
                reviews.aggregate(a=Avg('overall_rating'))['a'] or 0
            ),
            'rating_distribution': rating_dist,
            'as_tasker_reviews': reviews.filter(reviewer_type=REVIEWER_TYPE_CUSTOMER).count(),
            'as_customer_reviews': reviews.filter(reviewer_type=REVIEWER_TYPE_TASKER).count(),
            'trust_score': float(ReviewService.calculate_trust_score(user)),
        }
