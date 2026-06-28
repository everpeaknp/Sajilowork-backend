"""Project-level integration tests."""
from django.test import Client, TestCase


class HealthEndpointTests(TestCase):
    def test_health_returns_ok(self):
        response = Client().get('/health/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['status'], 'ok')
        self.assertEqual(payload['database'], 'ok')


class RegistrationTests(TestCase):
    def test_register_does_not_return_jwt_tokens(self):
        client = Client()
        response = client.post(
            '/api/v1/users/register/',
            data={
                'email': 'newuser@example.com',
                'password': 'SecurePass123',
                'password_confirm': 'SecurePass123',
                'first_name': 'New',
                'last_name': 'User',
                'role': 'customer',
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertTrue(payload.get('email_verification_required'))
        self.assertNotIn('access', payload)
        self.assertNotIn('refresh', payload)
        self.assertEqual(payload['user']['email'], 'newuser@example.com')

    def test_login_blocked_until_email_verified(self):
        from apps.users.models import User

        user = User.objects.create_user(
            email='unverified@example.com',
            password='SecurePass123',
            first_name='Test',
            last_name='User',
            role='customer',
        )
        user.email_verified = False
        user.save(update_fields=['email_verified'])

        client = Client()
        response = client.post(
            '/api/v1/auth/login/',
            data={'email': 'unverified@example.com', 'password': 'SecurePass123'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json().get('code'), 'email_not_verified')


class LoginThrottleTests(TestCase):
    def test_login_endpoint_exists_and_rejects_invalid_credentials(self):
        client = Client()
        response = client.post(
            '/api/v1/auth/login/',
            data={'email': 'nobody@example.com', 'password': 'wrong-password'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 401)


class VerifiedLoginTests(TestCase):
    def test_verified_user_receives_tokens(self):
        from apps.users.models import User

        user = User.objects.create_user(
            email='verified@example.com',
            password='SecurePass123',
            first_name='Verified',
            last_name='User',
            role='customer',
        )
        user.email_verified = True
        user.save(update_fields=['email_verified'])

        client = Client()
        response = client.post(
            '/api/v1/auth/login/',
            data={'email': 'verified@example.com', 'password': 'SecurePass123'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('access', payload)
        self.assertIn('refresh', payload)


class JobsApiAuthTests(TestCase):
    def test_jobs_mine_requires_authentication(self):
        response = Client().get('/api/v1/jobs/mine/')
        self.assertEqual(response.status_code, 401)
