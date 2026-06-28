"""Encryption utility tests."""
from django.test import TestCase

from utils.field_encryption import decrypt_secret, encrypt_secret


class FieldEncryptionTests(TestCase):
    def test_round_trip(self):
        plain = 'smtp-app-password-123'
        encrypted = encrypt_secret(plain)
        self.assertTrue(encrypted.startswith('enc:'))
        self.assertNotEqual(encrypted, plain)
        self.assertEqual(decrypt_secret(encrypted), plain)

    def test_legacy_plaintext_passthrough(self):
        self.assertEqual(decrypt_secret('legacy-plain'), 'legacy-plain')
