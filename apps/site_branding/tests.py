from unittest.mock import patch

from django.contrib.sites.models import Site
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.site_branding.admin import SiteAdminForm
from apps.site_branding.models import SiteBranding
from apps.site_branding.services import get_public_site_settings, resolve_public_site_name

CLOUDINARY_TEST_SETTINGS = {
    'CLOUDINARY_STORAGE': {
        'CLOUD_NAME': 'test-cloud',
        'API_KEY': 'test-key',
        'API_SECRET': 'test-secret',
    },
}


class SiteBrandingTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_branding_created_for_site(self):
        site = Site.objects.get_current()
        SiteBranding.objects.get_or_create(site=site)
        site.name = 'Sajilowork'
        site.save()

        settings = get_public_site_settings(site.pk)
        self.assertEqual(settings['site_name'], 'Sajilowork')
        self.assertIsNone(settings['favicon_url'])
        self.assertTrue(SiteBranding.objects.filter(site=site).exists())

    def test_placeholder_site_name_resolves_to_sajilowork(self):
        site = Site.objects.get_current()
        site.name = 'example.com'
        site.domain = 'localhost:3000'
        site.save()

        settings = get_public_site_settings(site.pk)
        self.assertEqual(settings['site_name'], 'Sajilowork')
        self.assertEqual(resolve_public_site_name('example.com'), 'Sajilowork')
        self.assertEqual(settings['site_domain'], 'www.sajilowork.com')

    @override_settings(**CLOUDINARY_TEST_SETTINGS)
    def test_admin_form_save_with_commit_false_uploads_favicon(self):
        site = Site.objects.get_current()
        branding, _ = SiteBranding.objects.get_or_create(site=site)
        branding.favicon_url = ''
        branding.save(update_fields=['favicon_url'])

        form = SiteAdminForm(
            data={
                'name': 'Sajilowork',
                'domain': site.domain,
                'remove_favicon': False,
            },
            files={
                'favicon': SimpleUploadedFile(
                    'favicon.png',
                    b'\x89PNG\r\n\x1a\n\x00',
                    content_type='image/png',
                ),
            },
            instance=site,
        )
        with patch('apps.site_branding.admin.upload_file_to_cloudinary') as mock_upload:
            mock_upload.return_value = {
                'secure_url': 'https://res.cloudinary.com/test-cloud/image/upload/favicon.png',
            }
            self.assertTrue(form.is_valid(), form.errors)
            form.save(commit=False)

        branding.refresh_from_db()
        self.assertEqual(
            branding.favicon_url,
            'https://res.cloudinary.com/test-cloud/image/upload/favicon.png',
        )

    @override_settings(**CLOUDINARY_TEST_SETTINGS)
    def test_site_settings_api_returns_cloudinary_favicon_url(self):
        site = Site.objects.get_current()
        branding, _ = SiteBranding.objects.get_or_create(site=site)
        branding.favicon_url = (
            'https://res.cloudinary.com/test-cloud/image/upload/v1/Sajilowork/Site/Favicon/favicon.png'
        )
        branding.save(update_fields=['favicon_url'])
        site.name = 'Sajilowork'
        site.save()

        response = self.client.get('/api/v1/site/settings/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['site_name'], 'Sajilowork')
        self.assertIn('res.cloudinary.com', response.data['favicon_url'])
