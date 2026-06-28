"""Dispute API authorization tests."""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.disputes.models import Dispute
from apps.tasks.models import Task
from apps.users.models import User
from decimal import Decimal


def _verified_user(*, email: str, role: str = 'customer') -> User:
    user = User.objects.create_user(
        email=email,
        password='SecurePass123',
        first_name='Test',
        last_name='User',
        role=role,
    )
    user.email_verified = True
    user.save(update_fields=['email_verified'])
    return user


class DisputeApiAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = _verified_user(email='owner@example.com', role='customer')
        self.tasker = _verified_user(email='tasker@example.com', role='tasker')
        self.stranger = _verified_user(email='stranger@example.com', role='customer')
        self.task = Task.objects.create(
            owner=self.owner,
            assigned_tasker=self.tasker,
            title='Disputed task',
            description='Task under dispute',
            budget_type='fixed',
            budget_amount=Decimal('1000.00'),
            location_type='remote',
            status='in_progress',
        )
        self.dispute = Dispute.objects.create(
            task=self.task,
            raised_by=self.owner,
            against=self.tasker,
            dispute_type='quality',
            title='Work quality issue',
            description='Deliverable did not match brief.',
            status='open',
        )

    def test_stranger_cannot_list_foreign_dispute(self):
        self.client.force_authenticate(user=self.stranger)
        response = self.client.get(f'/api/v1/disputes/{self.dispute.id}/')
        self.assertEqual(response.status_code, 404)

    def test_party_can_retrieve_dispute(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(f'/api/v1/disputes/{self.dispute.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['title'], 'Work quality issue')
