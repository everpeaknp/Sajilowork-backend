from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts import social_oauth

User = get_user_model()


class SocialAccountLinkingTests(TestCase):
    def test_google_login_links_existing_email_password_user(self):
        existing = User.objects.create_user(
            email='merge@example.com',
            username='mergeuser',
            password='SecurePass123!',
            first_name='Existing',
            last_name='User',
        )

        user = social_oauth.get_or_create_user_from_social(
            provider='google',
            provider_user_id='google-123',
            email='merge@example.com',
            first_name='Google',
            last_name='Name',
        )

        self.assertEqual(user.pk, existing.pk)
        self.assertEqual(user.google_id, 'google-123')
        self.assertTrue(user.has_usable_password())
        self.assertTrue(user.check_password('SecurePass123!'))
        self.assertEqual(User.objects.filter(email__iexact='merge@example.com').count(), 1)

    def test_google_login_merges_placeholder_social_user_into_existing_email(self):
        existing = User.objects.create_user(
            email='person@example.com',
            username='person',
            password='SecurePass123!',
        )
        placeholder = User.objects.create(
            email='google_google-999@social.sajilowork.local',
            username='google999',
            google_id='google-999',
        )
        placeholder.set_unusable_password()
        placeholder.save()

        user = social_oauth.get_or_create_user_from_social(
            provider='google',
            provider_user_id='google-999',
            email='person@example.com',
        )

        self.assertEqual(user.pk, existing.pk)
        self.assertEqual(user.google_id, 'google-999')
        placeholder.refresh_from_db()
        self.assertIsNone(placeholder.google_id)
