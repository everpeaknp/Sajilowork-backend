"""
Views for JWT authentication endpoints.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth import get_user_model
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
    ChangePasswordSerializer,
    AuthTokensResponseSerializer,
    MessageResponseSerializer,
    ErrorResponseSerializer,
    PasswordResetRequestResponseSerializer,
    TokenVerifyResponseSerializer,
)
from . import social_oauth

User = get_user_model()


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
def login_view(request):
    """
    User login endpoint.
    Returns JWT tokens and user information.
    """
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    email = serializer.validated_data['email']
    password = serializer.validated_data['password']
    
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response(
            {'error': 'Invalid credentials.'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    if not user.check_password(password):
        return Response(
            {'error': 'Invalid credentials.'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    if not user.is_active:
        return Response(
            {'error': 'Account is disabled.'},
            status=status.HTTP_403_FORBIDDEN
        )

    from apps.rules.services import ModerationService
    if ModerationService.is_user_suspended(user):
        user = ModerationService.refresh_suspension_state(user)
        if user.account_suspended:
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
def password_reset_request_view(request):
    """
    Request password reset.
    Sends reset email to user.
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    email = serializer.validated_data['email']
    
    try:
        user = User.objects.get(email=email)
        
        # Generate password reset token
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        # TODO: Send email with reset link
        # For now, return token in response (development only)
        reset_link = f"http://localhost:3000/reset-password?uid={uid}&token={token}"
        
        return Response({
            'message': 'Password reset email sent.',
            'reset_link': reset_link,  # Remove in production
        })
    except User.DoesNotExist:
        # Don't reveal if email exists
        return Response({
            'message': 'If an account exists with this email, a password reset link has been sent.',
        })


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
        if not default_token_generator.check_token(user, token):
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
    Verify user email with token.
    """
    serializer = EmailVerificationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    try:
        uid = request.data.get('uid')
        token = serializer.validated_data['token']
        
        # Decode user ID
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id)
        
        # Verify token
        if not default_token_generator.check_token(user, token):
            return Response(
                {'error': 'Invalid or expired token.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mark email as verified
        user.email_verified = True
        user.save(update_fields=['email_verified'])
        
        return Response({
            'message': 'Email verified successfully.',
        })
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return Response(
            {'error': 'Invalid token.'},
            status=status.HTTP_400_BAD_REQUEST
        )


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
    try:
        state = social_oauth.make_oauth_state(
            next_path=next_path,
            role=role,
            provider=provider,
        )
        if provider == 'google':
            url = social_oauth.google_login_url(state=state)
        else:
            url = social_oauth.facebook_login_url(state=state)
        return redirect(url)
    except social_oauth.OAuthConfigError as exc:
        return redirect(
            social_oauth.build_frontend_callback_url(
                error='oauth_not_configured',
                next_path=next_path,
            )
        )
    except Exception:
        return redirect(
            social_oauth.build_frontend_callback_url(
                error='oauth_start_failed',
                next_path=next_path,
            )
        )


def _oauth_callback_redirect(provider: str, request):
    next_path = '/discover'
    error_code = request.GET.get('error')
    if error_code:
        return redirect(
            social_oauth.build_frontend_callback_url(
                error=error_code,
                next_path=next_path,
            )
        )

    code = request.GET.get('code')
    state_raw = request.GET.get('state')
    if not code or not state_raw:
        return redirect(
            social_oauth.build_frontend_callback_url(
                error='oauth_missing_code',
                next_path=next_path,
            )
        )

    try:
        state = social_oauth.parse_oauth_state(state_raw)
        if state.get('provider') != provider:
            raise signing.BadSignature('Provider mismatch')
        next_path = _safe_next_path(state.get('next'))
        role = state.get('role', 'customer')

        if provider == 'google':
            profile = social_oauth.exchange_google_code(code)
            user = social_oauth.login_with_google_profile(profile, role=role)
        else:
            profile = social_oauth.exchange_facebook_code(code)
            user = social_oauth.login_with_facebook_profile(profile, role=role)

        access, refresh, _user_payload = social_oauth.issue_tokens_for_user(user)
        return redirect(
            social_oauth.build_frontend_callback_url(
                access=access,
                refresh=refresh,
                next_path=next_path,
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
            social_oauth.build_frontend_callback_url(error=err, next_path=next_path)
        )
    except (signing.BadSignature, signing.SignatureExpired):
        return redirect(
            social_oauth.build_frontend_callback_url(
                error='oauth_invalid_state',
                next_path=next_path,
            )
        )
    except Exception:
        return redirect(
            social_oauth.build_frontend_callback_url(
                error='oauth_failed',
                next_path=next_path,
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

