from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from apps.payments.models import Payment
from apps.tasks.models import Task
from apps.reviews.constants import REVIEWER_TYPE_CUSTOMER, REVIEWER_TYPE_TASKER
from apps.reviews.models import Review, ReviewInvitation
from apps.reviews.services import ReviewEligibilityError, ReviewService

User = get_user_model()


class ReviewSystemTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email='owner@test.com',
            password='pass12345',
            first_name='Owner',
            last_name='User',
        )
        self.tasker = User.objects.create_user(
            email='tasker@test.com',
            password='pass12345',
            first_name='Tasker',
            last_name='User',
        )
        self.task = Task.objects.create(
            owner=self.owner,
            assigned_tasker=self.tasker,
            title='Test task',
            description='Desc',
            status='completed',
            budget_amount=Decimal('1000.00'),
            completion_date=timezone.now(),
        )
        task_ct = ContentType.objects.get_for_model(Task)
        Payment.objects.create(
            payer=self.owner,
            payee=self.tasker,
            amount=Decimal('1000.00'),
            net_amount=Decimal('850.00'),
            status='released',
            payment_method='wallet',
            content_type=task_ct,
            object_id=self.task.id,
            completed_at=timezone.now(),
        )
        ReviewService.send_review_invitations(self.task)

    def test_resolve_reviewer_type_customer(self):
        self.assertEqual(
            ReviewService.resolve_reviewer_type(self.task, self.owner),
            REVIEWER_TYPE_CUSTOMER,
        )

    def test_resolve_reviewee_customer_reviews_tasker(self):
        reviewee = ReviewService.resolve_reviewee(self.task, REVIEWER_TYPE_CUSTOMER)
        self.assertEqual(reviewee, self.tasker)

    def test_resolve_reviewee_tasker_reviews_customer(self):
        reviewee = ReviewService.resolve_reviewee(self.task, REVIEWER_TYPE_TASKER)
        self.assertEqual(reviewee, self.owner)

    def test_customer_creates_review_for_tasker(self):
        review = ReviewService.create_review(
            task_id=self.task.id,
            reviewer=self.owner,
            rating=5,
            comment='Excellent work',
            tags=['professional', 'on_time'],
        )
        self.assertEqual(review.reviewer_type, REVIEWER_TYPE_CUSTOMER)
        self.assertEqual(review.reviewee, self.tasker)
        self.assertEqual(review.overall_rating, 5)

    def test_tasker_creates_review_for_customer(self):
        review = ReviewService.create_review(
            task_id=self.task.id,
            reviewer=self.tasker,
            rating=4,
            comment='Clear brief',
            tags=['friendly'],
        )
        self.assertEqual(review.reviewer_type, REVIEWER_TYPE_TASKER)
        self.assertEqual(review.reviewee, self.owner)

    def test_duplicate_review_blocked(self):
        ReviewService.create_review(
            task_id=self.task.id,
            reviewer=self.owner,
            rating=5,
        )
        with self.assertRaises(ReviewEligibilityError):
            ReviewService.create_review(
                task_id=self.task.id,
                reviewer=self.owner,
                rating=3,
            )

    def test_blocked_without_released_payment(self):
        task2 = Task.objects.create(
            owner=self.owner,
            assigned_tasker=self.tasker,
            title='Unpaid',
            description='x',
            status='completed',
            budget_amount=Decimal('500.00'),
        )
        with self.assertRaises(ReviewEligibilityError):
            ReviewService.create_review(
                task_id=task2.id,
                reviewer=self.owner,
                rating=5,
            )

    def test_invitations_created_for_both_parties(self):
        self.assertEqual(
            ReviewInvitation.objects.filter(task=self.task).count(),
            2,
        )

    def test_get_reviewable_tasks_for_reviewee(self):
        owner_tasks = ReviewService.get_reviewable_tasks_for_reviewee(
            self.owner,
            self.tasker.id,
        )
        self.assertEqual(len(owner_tasks), 1)
        self.assertEqual(owner_tasks[0].id, self.task.id)

        tasker_tasks = ReviewService.get_reviewable_tasks_for_reviewee(
            self.tasker,
            self.owner.id,
        )
        self.assertEqual(len(tasker_tasks), 1)

        ReviewService.create_review(
            task_id=self.task.id,
            reviewer=self.owner,
            rating=5,
        )
        owner_tasks_after = ReviewService.get_reviewable_tasks_for_reviewee(
            self.owner,
            self.tasker.id,
        )
        self.assertEqual(len(owner_tasks_after), 0)
