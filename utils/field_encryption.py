"""Fernet encryption helpers for sensitive stored fields."""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

ENC_PREFIX = 'enc:'


def _fernet() -> Fernet:
    material = (
        getattr(settings, 'SMTP_ENCRYPTION_KEY', None)
        or getattr(settings, 'SECRET_KEY', '')
        or 'django-insecure-change-this-in-production'
    )
    digest = hashlib.sha256(str(material).encode()).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    if not value:
        return value
    if value.startswith(ENC_PREFIX):
        return value
    token = _fernet().encrypt(value.encode()).decode()
    return f'{ENC_PREFIX}{token}'


def decrypt_secret(value: str) -> str:
    if not value:
        return value
    if not value.startswith(ENC_PREFIX):
        return value
    token = value[len(ENC_PREFIX) :]
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return value
