"""Password reset and email verification links + outbound mail."""

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import signing
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .auth_email_templates import (
    build_email_verification_html,
    build_email_verification_subject,
    build_email_verification_text,
    build_password_reset_html,
    build_password_reset_subject,
    build_password_reset_text,
)

EMAIL_VERIFY_SALT = 'sajilowork-email-verify'
EMAIL_VERIFY_MAX_AGE = 60 * 60 * 24 * 3  # 3 days

_token_generator = PasswordResetTokenGenerator()
_signer = signing.TimestampSigner(salt=EMAIL_VERIFY_SALT)


def frontend_url() -> str:
    configured = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000').rstrip('/')
    if not getattr(settings, 'DEBUG', True) and 'localhost' in configured:
        return 'https://www.sajilowork.com'
    return configured


def app_name() -> str:
    return getattr(settings, 'APP_NAME', 'Sajilowork')


def default_from_email() -> str:
    return getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@airtasker.com')


def encode_uid(user) -> str:
    return urlsafe_base64_encode(force_bytes(user.pk))


def build_password_reset_link(user) -> str:
    uid = encode_uid(user)
    token = _token_generator.make_token(user)
    return f'{frontend_url()}/reset-password?uid={uid}&token={token}'


def build_email_verification_link(user) -> str:
    signed = _signer.sign(str(user.pk))
    return f'{frontend_url()}/verify-email?token={signed}'


def send_password_reset_email(user) -> str:
    link = build_password_reset_link(user)
    display_name = user.get_full_name() or user.email.split('@')[0]
    subject = build_password_reset_subject()
    message = build_password_reset_text(display_name=display_name, link=link)
    html_message = build_password_reset_html(display_name=display_name, link=link)
    send_mail(
        subject=subject,
        message=message,
        from_email=default_from_email(),
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )
    return link


def send_email_verification_email(user) -> str | None:
    if user.email_verified:
        return None

    link = build_email_verification_link(user)
    display_name = user.get_full_name() or user.email.split('@')[0]
    subject = build_email_verification_subject()
    message = build_email_verification_text(display_name=display_name, link=link)
    html_message = build_email_verification_html(display_name=display_name, link=link)
    send_mail(
        subject=subject,
        message=message,
        from_email=default_from_email(),
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )
    return link


def verify_signed_email_token(token: str):
    try:
        uid = _signer.unsign(token, max_age=EMAIL_VERIFY_MAX_AGE)
        return uid, None
    except signing.SignatureExpired:
        return None, 'Verification link has expired.'
    except signing.BadSignature:
        return None, 'Invalid verification link.'


def check_password_reset_token(user, token: str) -> bool:
    return _token_generator.check_token(user, token)
