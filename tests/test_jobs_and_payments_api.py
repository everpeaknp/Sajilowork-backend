"""Integration tests for jobs API authorization and payment IDOR protection."""
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient

from apps.payments.models import Payment
from apps.tasks.models import Task
from apps.users.models import User


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


class JobsApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = _verified_user(email='employer@example.com', role='customer')
        self.other = _verified_user(email='other@example.com', role='customer')

    def test_customer_can_create_job(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            '/api/v1/jobs/',
            {
                'title': 'Office cleaner needed',
                'description': 'Weekly cleaning for a small office in Kathmandu.',
                'budget_type': 'fixed',
                'budget_amount': '5000.00',
                'location_type': 'remote',
                'is_public': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.content)
        payload = response.json()
        self.assertEqual(payload['title'], 'Office cleaner needed')
        self.assertIn('slug', payload)

    def test_non_owner_cannot_update_job(self):
        self.client.force_authenticate(user=self.owner)
        create = self.client.post(
            '/api/v1/jobs/',
            {
                'title': 'Garden maintenance',
                'description': 'Trim hedges and mow lawn once a week.',
                'budget_type': 'fixed',
                'budget_amount': '3000.00',
                'location_type': 'remote',
                'is_public': True,
            },
            format='json',
        )
        self.assertEqual(create.status_code, 201)
        slug = create.json()['slug']

        self.client.force_authenticate(user=self.other)
        response = self.client.patch(
            f'/api/v1/jobs/{slug}/',
            {'title': 'Hacked title'},
            format='json',
        )
        self.assertEqual(response.status_code, 403)

    def test_tasker_cannot_create_job(self):
        tasker = _verified_user(email='tasker@example.com', role='tasker')
        self.client.force_authenticate(user=tasker)
        response = self.client.post(
            '/api/v1/jobs/',
            {
                'title': 'Should fail',
                'description': 'Taskers must not create employer job listings.',
                'budget_type': 'fixed',
                'budget_amount': '1000.00',
                'location_type': 'remote',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 403)


class PaymentIdorTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.payer = _verified_user(email='payer@example.com', role='customer')
        self.payee = _verified_user(email='payee@example.com', role='tasker')
        self.stranger = _verified_user(email='stranger@example.com', role='customer')

        self.task = Task.objects.create(
            owner=self.payer,
            title='Private payment task',
            description='Used for payment IDOR test',
            budget_type='fixed',
            budget_amount=Decimal('2000.00'),
            location_type='remote',
            status='open',
        )
        ct = ContentType.objects.get_for_model(Task)
        self.payment = Payment.objects.create(
            payer=self.payer,
            payee=self.payee,
            content_type=ct,
            object_id=self.task.id,
            amount=Decimal('2000.00'),
            payment_type='task_payment',
            payment_method='wallet',
            status='held',
            net_amount=Decimal('1800.00'),
        )

    def test_stranger_cannot_retrieve_payment(self):
        self.client.force_authenticate(user=self.stranger)
        response = self.client.get(f'/api/v1/payments/payments/{self.payment.id}/')
        self.assertIn(response.status_code, (403, 404))

    def test_participant_can_retrieve_payment(self):
        self.client.force_authenticate(user=self.payer)
        response = self.client.get(f'/api/v1/payments/payments/{self.payment.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], str(self.payment.id))
