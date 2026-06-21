"""
OAuth helpers for Google and Facebook login (authorization code flow).
"""
from __future__ import annotations

import re
import secrets
import urllib.parse
from typing import Any

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.utils import timezone

from apps.users.user_media_utils import resolve_user_media_url
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

OAUTH_STATE_SALT = 'tasknepal-oauth-state'
OAUTH_STATE_MAX_AGE = 600  # 10 minutes


class OAuthConfigError(Exception):
    """Raised when provider credentials or URLs are not configured."""


def _backend_base() -> str:
    return getattr(settings, 'BACKEND_URL', 'http://localhost:8000').rstrip('/')


def _frontend_base() -> str:
    return getattr(settings, 'FRONTEND_URL', 'http://localhost:3000').rstrip('/')


def resolve_oauth_redirect_uri(provider: str, request=None) -> str:
    """Return the OAuth callback URL sent to Google/Facebook (must match console config)."""
    if provider == 'google':
        explicit = getattr(settings, 'GOOGLE_OAUTH_REDIRECT_URI', '') or ''
    else:
        explicit = getattr(settings, 'FACEBOOK_OAUTH_REDIRECT_URI', '') or ''
    if explicit:
        return explicit if explicit.endswith('/') else f'{explicit}/'
    if request is not None:
        return request.build_absolute_uri(f'/api/v1/auth/{provider}/callback/')
    return f'{_backend_base()}/api/v1/auth/{provider}/callback/'


def make_oauth_state(
    *,
    next_path: str,
    role: str,
    provider: str,
    redirect_uri: str,
) -> str:
    payload = {
        'next': next_path or '/discover',
        'role': role if role in ('customer', 'tasker') else 'customer',
        'provider': provider,
        'redirect_uri': redirect_uri,
        'nonce': secrets.token_urlsafe(8),
    }
    return signing.dumps(payload, salt=OAUTH_STATE_SALT)


def parse_oauth_state(state: str) -> dict[str, str]:
    data = signing.loads(state, salt=OAUTH_STATE_SALT, max_age=OAUTH_STATE_MAX_AGE)
    if not isinstance(data, dict):
        raise signing.BadSignature('Invalid OAuth state')
    return data


def _unique_username(base: str) -> str:
    slug = re.sub(r'[^a-zA-Z0-9_]', '', (base or 'user').lower())[:24] or 'user'
    candidate = slug
    counter = 0
    while User.objects.filter(username=candidate).exists():
        counter += 1
        candidate = f'{slug}{counter}'
    return candidate


def serialize_user_for_auth(user) -> dict[str, Any]:
    profile_image = resolve_user_media_url(None, getattr(user, 'profile_image', None))
    return {
        'id': str(user.id),
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'role': user.role,
        'is_verified': user.email_verified,
        'profile_image': profile_image,
    }


def issue_tokens_for_user(user) -> tuple[str, str, dict[str, Any]]:
    from apps.rules.services import ModerationService

    if not user.is_active:
        raise ValueError('Account is disabled.')
    if ModerationService.is_user_suspended(user):
        user = ModerationService.refresh_suspension_state(user)
        if user.account_suspended:
            raise ValueError('Account is temporarily suspended.')

    refresh = RefreshToken.for_user(user)
    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])
    return str(refresh.access_token), str(refresh), serialize_user_for_auth(user)


def build_frontend_callback_url(
    *,
    access: str | None = None,
    refresh: str | None = None,
    next_path: str = '/discover',
    error: str | None = None,
) -> str:
    params: dict[str, str] = {}
    if error:
        params['error'] = error
    else:
        params['access'] = access or ''
        params['refresh'] = refresh or ''
    if next_path:
        params['next'] = next_path
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v})
    return f'{_frontend_base()}/auth/callback?{query}'


def get_or_create_user_from_social(
    *,
    provider: str,
    provider_user_id: str,
    email: str | None,
    first_name: str = '',
    last_name: str = '',
    role: str = 'customer',
) -> User:
    provider_field = 'google_id' if provider == 'google' else 'facebook_id'
    lookup = {provider_field: provider_user_id}
    user = User.objects.filter(**lookup).first()
    if user:
        return user

    normalized_email = (email or '').strip().lower()
    if normalized_email:
        existing = User.objects.filter(email__iexact=normalized_email).first()
        if existing:
            if not getattr(existing, provider_field):
                setattr(existing, provider_field, provider_user_id)
                if not existing.email_verified and provider == 'google':
                    existing.email_verified = True
                existing.save(update_fields=[provider_field, 'email_verified'])
            return existing

    if not normalized_email:
        normalized_email = f'{provider}_{provider_user_id}@social.tasknepal.local'

    username_base = normalized_email.split('@')[0]
    user = User(
        email=normalized_email,
        username=_unique_username(username_base),
        first_name=(first_name or '')[:150],
        last_name=(last_name or '')[:150],
        role=role if role in ('customer', 'tasker') else 'customer',
        email_verified=bool(email),
        **{provider_field: provider_user_id},
    )
    user.set_unusable_password()
    user.save()
    return user


# --- Google ---


def google_login_url(*, state: str, redirect_uri: str) -> str:
    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '') or ''
    if not client_id:
        raise OAuthConfigError('Google OAuth is not configured (GOOGLE_CLIENT_ID).')

    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile',
        'access_type': 'online',
        'prompt': 'select_account',
        'state': state,
    }
    return 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode(params)


def exchange_google_code(code: str, *, redirect_uri: str) -> dict[str, Any]:
    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '') or ''
    client_secret = getattr(settings, 'GOOGLE_CLIENT_SECRET', '') or ''
    if not client_id or not client_secret:
        raise OAuthConfigError('Google OAuth is not configured.')

    token_resp = requests.post(
        'https://oauth2.googleapis.com/token',
        data={
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code',
        },
        timeout=15,
    )
    token_resp.raise_for_status()
    tokens = token_resp.json()
    access_token = tokens.get('access_token')
    if not access_token:
        raise ValueError('Google did not return an access token.')

    profile_resp = requests.get(
        'https://www.googleapis.com/oauth2/v2/userinfo',
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=15,
    )
    profile_resp.raise_for_status()
    return profile_resp.json()


def login_with_google_profile(profile: dict[str, Any], *, role: str) -> User:
    return get_or_create_user_from_social(
        provider='google',
        provider_user_id=str(profile.get('id', '')),
        email=profile.get('email'),
        first_name=profile.get('given_name') or '',
        last_name=profile.get('family_name') or '',
        role=role,
    )


# --- Facebook ---


def facebook_login_url(*, state: str, redirect_uri: str) -> str:
    app_id = getattr(settings, 'FACEBOOK_APP_ID', '') or ''
    if not app_id:
        raise OAuthConfigError('Facebook OAuth is not configured (FACEBOOK_APP_ID).')

    params = {
        'client_id': app_id,
        'redirect_uri': redirect_uri,
        'state': state,
        'scope': 'email,public_profile',
        'response_type': 'code',
    }
    return 'https://www.facebook.com/v21.0/dialog/oauth?' + urllib.parse.urlencode(params)


def exchange_facebook_code(code: str, *, redirect_uri: str) -> dict[str, Any]:
    app_id = getattr(settings, 'FACEBOOK_APP_ID', '') or ''
    app_secret = getattr(settings, 'FACEBOOK_APP_SECRET', '') or ''
    if not app_id or not app_secret:
        raise OAuthConfigError('Facebook OAuth is not configured.')

    token_resp = requests.get(
        'https://graph.facebook.com/v21.0/oauth/access_token',
        params={
            'client_id': app_id,
            'client_secret': app_secret,
            'redirect_uri': redirect_uri,
            'code': code,
        },
        timeout=15,
    )
    token_resp.raise_for_status()
    tokens = token_resp.json()
    access_token = tokens.get('access_token')
    if not access_token:
        raise ValueError('Facebook did not return an access token.')

    profile_resp = requests.get(
        'https://graph.facebook.com/me',
        params={
            'fields': 'id,email,first_name,last_name,picture',
            'access_token': access_token,
        },
        timeout=15,
    )
    profile_resp.raise_for_status()
    return profile_resp.json()


def login_with_facebook_profile(profile: dict[str, Any], *, role: str) -> User:
    return get_or_create_user_from_social(
        provider='facebook',
        provider_user_id=str(profile.get('id', '')),
        email=profile.get('email'),
        first_name=profile.get('first_name') or '',
        last_name=profile.get('last_name') or '',
        role=role,
    )
