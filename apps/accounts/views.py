"""
Views for JWT authentication endpoints.
"""
import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth import get_user_model
from django.conf import settings
from django.shortcuts import redirect
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.utils import timezone

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse, OpenApiExample

from .serializers import (
    CustomTokenObtainPairSerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    EmailVerificationSerializer,
    ResendVerificationEmailSerializer,
    ChangePasswordSerializer,
    AuthTokensResponseSerializer,
    MessageResponseSerializer,
    ErrorResponseSerializer,
    PasswordResetRequestResponseSerializer,
    TokenVerifyResponseSerializer,
)
from . import social_oauth
from . import email_auth
from utils.throttles import LoginRateThrottle, PasswordResetRateThrottle

User = get_user_model()
logger = logging.getLogger(__name__)


@extend_schema_view(
    post=extend_schema(
        tags=['Authentication'],
        auth=[],
        summary='Obtain JWT token pair',
        description='Standard SimpleJWT login. Returns `access` and `refresh` tokens.',
    ),
)
class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom JWT token obtain view that includes user information.
    """
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [LoginRateThrottle]


@extend_schema(
    tags=['Authentication'],
    auth=[],
    summary='Login (recommended for apps)',
    description='Returns JWT access/refresh tokens plus user profile fields (role, avatar, etc.).',
    request=LoginSerializer,
    responses={
        200: AuthTokensResponseSerializer,
        401: OpenApiResponse(response=ErrorResponseSerializer, description='Invalid credentials'),
        403: OpenApiResponse(response=ErrorResponseSerializer, description='Account disabled or suspended'),
    },
    examples=[
        OpenApiExample(
            'Login request',
            value={'email': 'test@example.com', 'password': 'Test123456'},
            request_only=True,
        ),
    ],
)
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def login_view(request):
    """
    User login endpoint.
    Returns JWT tokens and user information.
    """
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    email = serializer.validated_data['email']
    password = serializer.validated_data['password']
    client_ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR', '')

    user = User.objects.filter(email__iexact=email).first()
    if not user:
        logger.warning("Login failed: user not found for email=%s ip=%s", email, client_ip)
        return Response(
            {'error': 'Invalid credentials.'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    if not user.has_usable_password():
        if user.google_id:
            social_hint = 'Sign in with Google'
        elif user.facebook_id:
            social_hint = 'Sign in with Facebook'
        else:
            social_hint = 'Use Forgot password to set a password'
        logger.warning("Login failed: social-only account email=%s user_id=%s ip=%s", email, user.id, client_ip)
        return Response(
            {
                'error': (
                    f'This account does not have a password yet. {social_hint}, '
                    'or use Forgot password to add one to this email.'
                ),
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.check_password(password):
        logger.warning("Login failed: bad password email=%s user_id=%s ip=%s", email, user.id, client_ip)
        return Response(
            {'error': 'Invalid credentials.'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    if not user.is_active:
        logger.warning("Login failed: inactive account email=%s user_id=%s ip=%s", email, user.id, client_ip)
        return Response(
            {'error': 'Account is disabled.'},
            status=status.HTTP_403_FORBIDDEN
        )

    if not user.email_verified:
        logger.warning("Login failed: email not verified email=%s user_id=%s ip=%s", email, user.id, client_ip)
        return Response(
            {
                'error': 'Please verify your email before signing in. Check your inbox or request a new verification link.',
                'code': 'email_not_verified',
                'email': user.email,
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    from apps.rules.services import ModerationService
    if ModerationService.is_user_suspended(user):
        user = ModerationService.refresh_suspension_state(user)
        if user.account_suspended:
            logger.warning("Login failed: suspended account email=%s user_id=%s ip=%s", email, user.id, client_ip)
            return Response(
                {
                    'error': 'Account is temporarily suspended.',
                    'suspended_until': user.suspended_until.isoformat() if user.suspended_until else None,
                    'reason': user.suspension_reason,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
    
    # Generate tokens
    refresh = RefreshToken.for_user(user)
    
    # Update last login
    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])
    logger.info("Login succeeded email=%s user_id=%s ip=%s", email, user.id, client_ip)
    
    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': social_oauth.serialize_user_for_auth(user),
    })


@extend_schema(
    tags=['Authentication'],
    summary='Logout (blacklist refresh token)',
    request=LogoutSerializer,
    responses={
        200: MessageResponseSerializer,
        400: OpenApiResponse(response=ErrorResponseSerializer, description='Invalid refresh token'),
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    User logout endpoint.
    Blacklists the refresh token.
    """
    serializer = LogoutSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    try:
        refresh_token = serializer.validated_data['refresh']
        token = RefreshToken(refresh_token)
        token.blacklist()
        
        return Response(
            {'message': 'Successfully logged out.'},
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {'error': 'Invalid token.'},
            status=status.HTTP_400_BAD_REQUEST
        )


@extend_schema(
    tags=['Authentication'],
    auth=[],
    summary='Request password reset',
    request=PasswordResetRequestSerializer,
    responses={200: PasswordResetRequestResponseSerializer},
)
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetRateThrottle])
def password_reset_request_view(request):
    """
    Request password reset.
    Sends reset email to user.
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    email = (serializer.validated_data['email'] or '').strip()
    user = User.objects.filter(email__iexact=email).first()

    reset_link = None
    if user:
        try:
            reset_link = email_auth.send_password_reset_email(user)
        except Exception:
            if settings.DEBUG:
                raise
            # Do not reveal delivery failures to the client.

    payload = {
        'message': 'If an account exists with this email, a password reset link has been sent.',
    }
    if settings.DEBUG and reset_link:
        payload['reset_link'] = reset_link

    return Response(payload)


@extend_schema(
    tags=['Authentication'],
    auth=[],
    summary='Confirm password reset',
    request=PasswordResetConfirmSerializer,
    responses={
        200: MessageResponseSerializer,
        400: OpenApiResponse(response=ErrorResponseSerializer, description='Invalid/expired token'),
    },
)
@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_confirm_view(request):
    """
    Confirm password reset with token.
    """
    serializer = PasswordResetConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    try:
        uid = request.data.get('uid')
        token = serializer.validated_data['token']
        password = serializer.validated_data['password']
        
        # Decode user ID
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id)
        
        # Verify token
        if not email_auth.check_password_reset_token(user, token):
            return Response(
                {'error': 'Invalid or expired token.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Set new password
        user.set_password(password)
        user.save()
        
        return Response({
            'message': 'Password has been reset successfully.',
        })
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return Response(
            {'error': 'Invalid token.'},
            status=status.HTTP_400_BAD_REQUEST
        )


@extend_schema(
    tags=['Authentication'],
    auth=[],
    summary='Verify email',
    request=EmailVerificationSerializer,
    responses={
        200: MessageResponseSerializer,
        400: OpenApiResponse(response=ErrorResponseSerializer, description='Invalid/expired token'),
    },
)
@api_view(['POST'])
@permission_classes([AllowAny])
def verify_email_view(request):
    """
    Verify user email with signed token from the verification link.
    """
    serializer = EmailVerificationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    token = serializer.validated_data['token']
    user_id, error = email_auth.verify_signed_email_token(token)
    if error:
        return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.filter(pk=user_id).first()
    if not user:
        return Response({'error': 'Invalid verification link.'}, status=status.HTTP_400_BAD_REQUEST)

    if not user.email_verified:
        user.email_verified = True
        user.save(update_fields=['email_verified'])

    return Response({'message': 'Email verified successfully.'})


@extend_schema(
    tags=['Authentication'],
    auth=[],
    summary='Resend verification email',
    request=ResendVerificationEmailSerializer,
    responses={200: MessageResponseSerializer},
)
@api_view(['POST'])
@permission_classes([AllowAny])
def resend_verification_email_view(request):
    """Send another email verification link."""
    serializer = ResendVerificationEmailSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    email = (serializer.validated_data['email'] or '').strip()
    user = User.objects.filter(email__iexact=email).first()

    verification_link = None
    if user and not user.email_verified:
        try:
            verification_link = email_auth.send_email_verification_email(user)
        except Exception:
            if settings.DEBUG:
                raise

    payload = {
        'message': 'If an account exists for that email, a verification link has been sent.',
    }
    if settings.DEBUG and verification_link:
        payload['verification_link'] = verification_link

    return Response(payload)


@extend_schema(
    tags=['Authentication'],
    summary='Change password',
    request=ChangePasswordSerializer,
    responses={
        200: MessageResponseSerializer,
        400: OpenApiResponse(response=ErrorResponseSerializer, description='Validation error'),
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    """
    Change user password.
    Requires old password for verification.
    """
    serializer = ChangePasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    user = request.user
    old_password = serializer.validated_data['old_password']
    new_password = serializer.validated_data['new_password']
    
    # Verify old password
    if not user.check_password(old_password):
        return Response(
            {'error': 'Current password is incorrect.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Set new password
    user.set_password(new_password)
    user.save()
    
    return Response({
        'message': 'Password changed successfully.',
    })


@extend_schema(
    tags=['Authentication'],
    summary='Verify current JWT token',
    responses={200: TokenVerifyResponseSerializer},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def verify_token_view(request):
    """
    Verify if the current token is valid.
    Returns user information.
    """
    user = request.user
    
    return Response({
        'valid': True,
        'user': social_oauth.serialize_user_for_auth(user),
    })


def _safe_next_path(raw: str | None) -> str:
    if raw and raw.startswith('/') and not raw.startswith('//'):
        return raw
    return '/discover'


def _oauth_login_redirect(provider: str, request):
    next_path = _safe_next_path(request.GET.get('next'))
    role = request.GET.get('role', 'customer')
    frontend_base = social_oauth.resolve_frontend_origin(request=request)
    try:
        redirect_uri = social_oauth.resolve_oauth_redirect_uri(provider, request)
        state = social_oauth.make_oauth_state(
            next_path=next_path,
            role=role,
            provider=provider,
            redirect_uri=redirect_uri,
            frontend_origin=frontend_base,
        )
        if provider == 'google':
            url = social_oauth.google_login_url(state=state, redirect_uri=redirect_uri)
        else:
            url = social_oauth.facebook_login_url(state=state, redirect_uri=redirect_uri)
        return redirect(url)
    except social_oauth.OAuthConfigError as exc:
        return redirect(
            social_oauth.build_frontend_callback_url(
                error='oauth_not_configured',
                next_path=next_path,
                frontend_base=frontend_base,
            )
        )
    except Exception:
        return redirect(
            social_oauth.build_frontend_callback_url(
                error='oauth_start_failed',
                next_path=next_path,
                frontend_base=frontend_base,
            )
        )


def _oauth_callback_redirect(provider: str, request):
    next_path = '/discover'
    frontend_base = social_oauth.resolve_frontend_origin(request=request)
    error_code = request.GET.get('error')
    if error_code:
        return redirect(
            social_oauth.build_frontend_callback_url(
                error=error_code,
                next_path=next_path,
                frontend_base=frontend_base,
            )
        )

    code = request.GET.get('code')
    state_raw = request.GET.get('state')
    if not code or not state_raw:
        return redirect(
            social_oauth.build_frontend_callback_url(
                error='oauth_missing_code',
                next_path=next_path,
                frontend_base=frontend_base,
            )
        )

    try:
        state = social_oauth.parse_oauth_state(state_raw)
        if state.get('provider') != provider:
            raise signing.BadSignature('Provider mismatch')
        next_path = _safe_next_path(state.get('next'))
        role = state.get('role', 'customer')
        frontend_base = social_oauth.resolve_frontend_origin(state=state, request=request)
        redirect_uri = state.get('redirect_uri') or social_oauth.resolve_oauth_redirect_uri(
            provider, request
        )

        if provider == 'google':
            profile = social_oauth.exchange_google_code(code, redirect_uri=redirect_uri)
            user = social_oauth.login_with_google_profile(profile, role=role)
        else:
            profile = social_oauth.exchange_facebook_code(code, redirect_uri=redirect_uri)
            user = social_oauth.login_with_facebook_profile(profile, role=role)

        access, refresh, _user_payload = social_oauth.issue_tokens_for_user(user)
        return redirect(
            social_oauth.build_frontend_callback_url(
                access=access,
                refresh=refresh,
                next_path=next_path,
                frontend_base=frontend_base,
            )
        )
    except ValueError as exc:
        msg = str(exc).lower()
        if 'suspended' in msg:
            err = 'account_suspended'
        elif 'disabled' in msg:
            err = 'account_disabled'
        else:
            err = 'oauth_failed'
        return redirect(
            social_oauth.build_frontend_callback_url(
                error=err,
                next_path=next_path,
                frontend_base=frontend_base,
            )
        )
    except (signing.BadSignature, signing.SignatureExpired):
        return redirect(
            social_oauth.build_frontend_callback_url(
                error='oauth_invalid_state',
                next_path=next_path,
                frontend_base=frontend_base,
            )
        )
    except Exception:
        return redirect(
            social_oauth.build_frontend_callback_url(
                error='oauth_failed',
                next_path=next_path,
                frontend_base=frontend_base,
            )
        )


@extend_schema(
    tags=['Authentication'],
    auth=[],
    summary='Start Google OAuth login',
    description='Redirects the browser to Google. After consent, returns to the frontend with JWT tokens.',
)
def google_login_view(request):
    return _oauth_login_redirect('google', request)


@extend_schema(
    tags=['Authentication'],
    auth=[],
    summary='Google OAuth callback',
    description='Handles Google redirect, creates or links the user, then redirects to the frontend callback page.',
)
def google_callback_view(request):
    return _oauth_callback_redirect('google', request)


@extend_schema(
    tags=['Authentication'],
    auth=[],
    summary='Start Facebook OAuth login',
)
def facebook_login_view(request):
    return _oauth_login_redirect('facebook', request)


@extend_schema(
    tags=['Authentication'],
    auth=[],
    summary='Facebook OAuth callback',
)
def facebook_callback_view(request):
    return _oauth_callback_redirect('facebook', request)
