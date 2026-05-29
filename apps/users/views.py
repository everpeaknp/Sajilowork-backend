"""
Views for User management.
"""
import os
import uuid
from rest_framework import viewsets, status, generics, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db.models import Q, Count, Avg
from django_filters.rest_framework import DjangoFilterBackend
from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str

from .models import User, UserSkill, UserBadge, UserDocument, PortfolioItem, UserFollow
from .serializers import (
    UserListSerializer, UserDetailSerializer, UserProfileSerializer,
    UserRegistrationSerializer, ChangePasswordSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
    EmailVerificationSerializer, UserStatsSerializer,
    TaskerPublicProfileSerializer, PublicProfileSerializer, UserSkillSerializer,
    UserBadgeSerializer, UserBadgeCreateSerializer, UserDocumentSerializer,
    PortfolioItemSerializer,
)
from .badge_service import sync_auto_badges, request_or_sync_badge
from .portfolio_service import (
    ALLOWED_PORTFOLIO_CONTENT_TYPES,
    MAX_PORTFOLIO_BYTES,
    MAX_PORTFOLIO_ITEMS,
    build_portfolio_file_url,
    delete_portfolio_file,
    delete_portfolio_user_document,
    get_public_portfolio_items,
    portfolio_document_status_map,
    save_portfolio_upload,
    sync_portfolio_user_document,
)
from .document_service import (
    ALLOWED_DOCUMENT_CONTENT_TYPES,
    MAX_DOCUMENT_BYTES,
    build_document_url,
    delete_document_file,
    save_user_document_upload,
    upsert_user_document,
)
from .permissions import IsOwnerOrReadOnly, IsOwner

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for User CRUD operations.
    """
    queryset = User.objects.filter(is_active=True)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['first_name', 'last_name', 'email', 'username', 'bio', 'city']
    ordering_fields = ['date_joined', 'average_rating', 'tasks_completed']
    filterset_fields = ['role', 'is_verified_tasker', 'city', 'country']
    
    def get_serializer_class(self):
        """Return appropriate serializer class."""
        if self.action == 'list':
            return UserListSerializer
        elif self.action in ['retrieve', 'me']:
            return UserDetailSerializer
        elif self.action in ['update', 'partial_update']:
            return UserProfileSerializer
        return UserDetailSerializer
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in [
            'create',
            'register',
            'profile_by_username',
            'public_profile',
            'taskers',
            'follow_status',
            'reviews',
        ]:
            return [AllowAny()]
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsOwner()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['get'], url_path='reviews', permission_classes=[AllowAny])
    def reviews(self, request, pk=None):
        """
        GET /api/v1/users/{id}/reviews/
        Public reviews received by this user + statistics.
        """
        from apps.reviews.services import ReviewService
        from apps.reviews.serializers import ReviewListSerializer, UserReviewStatsSerializer

        user = self.get_object()
        reviews = ReviewService.get_reviews_received(user)
        stats = ReviewService.get_review_statistics(user)
        return Response({
            'user_id': str(user.id),
            'statistics': UserReviewStatsSerializer(stats).data,
            'count': reviews.count(),
            'results': ReviewListSerializer(reviews, many=True, context={'request': request}).data,
        })
    
    @action(detail=False, methods=['get', 'patch'], permission_classes=[IsAuthenticated])
    def me(self, request):
        """Get or update current user profile."""
        if request.method == 'PATCH':
            serializer = UserProfileSerializer(
                request.user,
                data=request.data,
                partial=True,
                context={'request': request},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(
                UserDetailSerializer(request.user, context={'request': request}).data
            )

        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['patch'], permission_classes=[IsAuthenticated])
    def update_profile(self, request):
        """Update current user profile (legacy endpoint)."""
        serializer = UserProfileSerializer(
            request.user,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            UserDetailSerializer(request.user, context={'request': request}).data
        )
    
    @action(detail=False, methods=['post'], url_path='me/change-password', permission_classes=[IsAuthenticated])
    def change_password(self, request):
        """Change user password."""
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        return Response({
            'message': 'Password changed successfully.'
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def stats(self, request):
        """Get user statistics."""
        serializer = UserStatsSerializer(request.user)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def public_profile(self, request, pk=None):
        """Get public profile of a tasker."""
        user = self.get_object()
        if user.role != 'tasker':
            return Response({
                'error': 'This user is not a tasker.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = TaskerPublicProfileSerializer(user, context={'request': request})
        return Response(serializer.data)

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[AllowAny],
        url_path=r'profile/(?P<username>[^/]+)',
    )
    def profile_by_username(self, request, username=None):
        """Public profile by username or user id (for /users/[slug])."""
        slug = (username or '').strip()
        if not slug:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        lookup = Q(username__iexact=slug)
        try:
            uuid.UUID(slug)
            lookup |= Q(id=slug)
        except ValueError:
            pass

        user = (
            User.objects.filter(is_active=True)
            .filter(lookup)
            .prefetch_related('skills', 'badges')
            .first()
        )
        if not user:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PublicProfileSerializer(user, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def follow_status(self, request, pk=None):
        """Follow state and follower count for a user."""
        target = self.get_object()
        is_following = False
        if request.user.is_authenticated:
            is_following = UserFollow.objects.filter(
                follower=request.user, following=target
            ).exists()
        return Response({
            'is_following': is_following,
            'followers_count': target.user_followers.count(),
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def follow(self, request, pk=None):
        """Follow another user."""
        target = self.get_object()
        if target.id == request.user.id:
            return Response(
                {'error': 'You cannot follow yourself.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        UserFollow.objects.get_or_create(follower=request.user, following=target)
        return Response({
            'is_following': True,
            'followers_count': target.user_followers.count(),
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def unfollow(self, request, pk=None):
        """Unfollow a user."""
        target = self.get_object()
        UserFollow.objects.filter(follower=request.user, following=target).delete()
        return Response({
            'is_following': False,
            'followers_count': target.user_followers.count(),
        })
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def taskers(self, request):
        """List all verified taskers."""
        taskers = User.objects.filter(
            role='tasker',
            is_active=True,
            is_verified_tasker=True
        ).order_by('-average_rating', '-tasks_completed')
        
        # Apply filters
        city = request.query_params.get('city')
        min_rating = request.query_params.get('min_rating')
        skill = request.query_params.get('skill')
        
        if city:
            taskers = taskers.filter(city__icontains=city)
        if min_rating:
            taskers = taskers.filter(average_rating__gte=float(min_rating))
        if skill:
            taskers = taskers.filter(skills__name__icontains=skill)
        
        page = self.paginate_queryset(taskers)
        if page is not None:
            serializer = TaskerPublicProfileSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = TaskerPublicProfileSerializer(taskers, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'], url_path='me/upload-image', permission_classes=[IsAuthenticated])
    def upload_image(self, request):
        """Upload profile image to local media folder."""
        file = request.FILES.get('profile_image')
        if not file:
            return Response(
                {'error': 'No image provided.', 'detail': 'Please select an image file to upload.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate file type
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        if file.content_type not in allowed_types:
            return Response(
                {'error': 'Invalid file type. Only JPG, PNG, GIF, and WebP are allowed.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate file size (5MB max)
        if file.size > 5 * 1024 * 1024:
            return Response(
                {'error': 'File size exceeds 5MB limit.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Delete old profile image if exists
            if request.user.profile_image:
                old_image_path = request.user.profile_image.path
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)
            
            # Save new profile image
            request.user.profile_image = file
            request.user.save()
            
            # Return updated user data
            serializer = UserDetailSerializer(request.user, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': f'Failed to upload image: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], url_path='me/deactivate', permission_classes=[IsAuthenticated])
    def deactivate(self, request):
        """Deactivate current user account."""
        request.user.is_active = False
        request.user.save()
        return Response({'message': 'Account deactivated successfully.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='me/delete', permission_classes=[IsAuthenticated])
    def delete_account(self, request):
        """Delete current user account."""
        password = request.data.get('password')
        if not password or not request.user.check_password(password):
            return Response({'error': 'Invalid password.'}, status=status.HTTP_400_BAD_REQUEST)
        request.user.delete()
        return Response({'message': 'Account deleted successfully.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def update_online_status(self, request):
        """Update user online status."""
        is_online = request.data.get('is_online', True)
        request.user.update_online_status(is_online)
        return Response({
            'message': 'Online status updated.',
            'is_online': request.user.is_online
        })
    
    @action(detail=True, methods=['get'], url_path='portfolio', permission_classes=[AllowAny])
    def user_portfolio(self, request, pk=None):
        """Get portfolio items for a specific user."""
        user = self.get_object()
        portfolio_items = get_public_portfolio_items(user)
        doc_map = portfolio_document_status_map(user)
        serializer = PortfolioItemSerializer(
            portfolio_items,
            many=True,
            context={'request': request, 'portfolio_doc_map': doc_map},
        )
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='me/send-verification-code', permission_classes=[IsAuthenticated])
    def send_verification_code(self, request):
        """Send phone verification code via SMS."""
        phone = request.data.get('phone')
        if not phone:
            return Response(
                {'error': 'Phone number is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # TODO: Integrate with SMS service (Twilio, AWS SNS, etc.)
        # For now, generate a 6-digit code and store it temporarily
        import random
        verification_code = str(random.randint(100000, 999999))
        
        # Store code in cache/session (expires in 10 minutes)
        # In production, use Redis or similar
        request.session[f'phone_verification_{phone}'] = verification_code
        
        # TODO: Send SMS with verification code
        # For development, just return success
        print(f"Verification code for {phone}: {verification_code}")
        
        return Response({
            'message': 'Verification code sent successfully.',
            'phone': phone
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'], url_path='me/verify-phone', permission_classes=[IsAuthenticated])
    def verify_phone(self, request):
        """Verify phone number with code."""
        phone = request.data.get('phone')
        code = request.data.get('code')
        
        if not phone or not code:
            return Response(
                {'error': 'Phone number and verification code are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify code from session
        stored_code = request.session.get(f'phone_verification_{phone}')
        
        if not stored_code:
            return Response(
                {'error': 'Verification code expired or not found. Please request a new code.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if stored_code != code:
            return Response(
                {'error': 'Invalid verification code.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update user phone and mark as verified
        request.user.phone = phone
        request.user.phone_verified = True
        request.user.save(update_fields=['phone', 'phone_verified'])
        sync_auto_badges(request.user)

        # Clear verification code from session
        del request.session[f'phone_verification_{phone}']
        
        serializer = UserDetailSerializer(request.user, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'], url_path='me/link-bank-account', permission_classes=[IsAuthenticated])
    def link_bank_account(self, request):
        """Link bank account for payments (supports eSewa and traditional bank accounts)."""
        account_holder_name = request.data.get('account_holder_name')
        bsb_number = request.data.get('bsb_number', '')  # Optional for eSewa
        account_number = request.data.get('account_number', '')  # Optional for eSewa
        
        if not account_holder_name:
            return Response(
                {'error': 'Account holder name is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # TODO: Integrate with payout providers (eSewa, Khalti, bank transfer)
        # For now, just mark the user as having a payment method
        # In production, this would:
        # 1. Record payout destination (eSewa / Khalti / bank)
        # 2. Store encrypted bank details
        # 3. Verify account ownership
        # 4. Create a PaymentMethod model entry
        
        account_type = 'esewa' if not account_number else 'bank'
        
        # Mark user as having a payment method
        request.user.has_payment_method = True
        request.user.save(update_fields=['has_payment_method'])
        sync_auto_badges(request.user)

        return Response({
            'success': True,
            'message': f'{account_type.upper()} account linked successfully.',
            'data': {
                'account_holder_name': account_holder_name,
                'account_type': account_type,
                'has_payment_method': True
            }
        }, status=status.HTTP_200_OK)


class PortfolioView(generics.ListCreateAPIView):
    """
    GET  /users/me/portfolio/  - list current user's portfolio items
    POST /users/me/portfolio/  - upload a new portfolio item
    """
    serializer_class = PortfolioItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PortfolioItem.objects.filter(user=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['portfolio_doc_map'] = portfolio_document_status_map(self.request.user)
        return context

    def create(self, request, *args, **kwargs):
        if PortfolioItem.objects.filter(user=request.user).count() >= MAX_PORTFOLIO_ITEMS:
            return Response(
                {'error': f'Maximum {MAX_PORTFOLIO_ITEMS} portfolio items allowed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        if file.size > MAX_PORTFOLIO_BYTES:
            return Response(
                {'error': 'File size exceeds 5MB limit.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        content_type = file.content_type or ''
        if content_type not in ALLOWED_PORTFOLIO_CONTENT_TYPES:
            return Response(
                {'error': 'Invalid file type. Only JPG, PNG, PDF, and TXT files are allowed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        title = (request.data.get('title') or file.name).strip()[:255]
        description = (request.data.get('description') or '').strip()

        storage_path = save_portfolio_upload(request.user, file)
        file_url = build_portfolio_file_url(request, storage_path)

        portfolio_item = PortfolioItem.objects.create(
            user=request.user,
            title=title,
            description=description,
            file=file_url,
            file_type=content_type,
            file_size=file.size,
        )

        sync_portfolio_user_document(
            request.user,
            portfolio_item,
            document_url=file_url,
        )

        doc_map = portfolio_document_status_map(request.user)
        serializer = self.get_serializer(
            portfolio_item,
            context={**self.get_serializer_context(), 'portfolio_doc_map': doc_map},
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PortfolioDetailView(generics.DestroyAPIView):
    """
    DELETE /users/me/portfolio/<item_id>/  - delete a portfolio item
    """
    serializer_class = PortfolioItemSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_queryset(self):
        return PortfolioItem.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        delete_portfolio_user_document(instance.user, instance.id)
        delete_portfolio_file(instance.file)
        instance.delete()


class UserSkillViewSet(viewsets.ModelViewSet):
    """ViewSet for managing user skills."""
    
    serializer_class = UserSkillSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return skills for current user."""
        return UserSkill.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Create skill for current user."""
        serializer.save(user=self.request.user)


class UserBadgeViewSet(viewsets.GenericViewSet):
    """List and request verification badges for the current user."""

    serializer_class = UserBadgeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserBadge.objects.filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        sync_auto_badges(request.user)
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        create_serializer = UserBadgeCreateSerializer(data=request.data)
        create_serializer.is_valid(raise_exception=True)
        badge_type = create_serializer.validated_data['badge_type']
        document_number = create_serializer.validated_data.get('document_number', '')
        uploaded_file = (
            request.FILES.get('verification_document')
            or request.FILES.get('file')
        )
        badge = request_or_sync_badge(
            request.user,
            badge_type,
            uploaded_file=uploaded_file,
            document_number=document_number,
            custom_name=create_serializer.validated_data.get('name', ''),
            custom_description=create_serializer.validated_data.get('description', ''),
        )
        if badge.verification_document and badge.badge_type in (
            'police_check',
            'electrical_licence',
            'plumbing_licence',
            'custom_licence',
        ):
            from .badge_service import _sync_user_document_for_badge

            document_url = request.build_absolute_uri(badge.verification_document.url)
            _sync_user_document_for_badge(
                request.user,
                badge,
                document_url=document_url,
            )
        output = self.get_serializer(badge)
        return Response(output.data, status=status.HTTP_201_CREATED)


class UserDocumentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing user documents."""
    
    serializer_class = UserDocumentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return documents for current user."""
        return UserDocument.objects.filter(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        """
        POST /users/me/documents/ (multipart)
        Fields:
          - document_type: one of UserDocument.DOCUMENT_TYPES
          - document_number: optional reference
          - file: required (jpg/png/pdf)
        """
        document_type = (request.data.get('document_type') or '').strip()
        document_number = (request.data.get('document_number') or '').strip()
        uploaded_file = request.FILES.get('file') or request.FILES.get('document')

        if not document_type:
            return Response({'error': 'document_type is required.'}, status=status.HTTP_400_BAD_REQUEST)

        if not uploaded_file:
            return Response({'error': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        if uploaded_file.size > MAX_DOCUMENT_BYTES:
            return Response({'error': 'File size exceeds 5MB limit.'}, status=status.HTTP_400_BAD_REQUEST)

        content_type = uploaded_file.content_type or ''
        if content_type not in ALLOWED_DOCUMENT_CONTENT_TYPES:
            return Response(
                {'error': 'Invalid file type. Only JPG, PNG, and PDF files are allowed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        storage_path = save_user_document_upload(request.user, uploaded_file)
        document_url = build_document_url(request, storage_path)

        doc = upsert_user_document(
            user=request.user,
            document_type=document_type,
            document_url=document_url,
            document_number=document_number,
        )

        serializer = self.get_serializer(doc, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        delete_document_file(instance.document_url)
        instance.delete()


class UserRegistrationView(generics.CreateAPIView):
    """View for user registration."""
    
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        """Register new user."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = serializer.save()
        except IntegrityError:
            # Defensive: should be prevented by serializer validation, but keep
            # this to avoid leaking a 500 if DB uniqueness is hit.
            return Response(
                {
                    'success': False,
                    'error': {
                        'message': 'Registration failed.',
                        'details': {'email': ['A user with this email already exists.']},
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # TODO: Send verification email
        
        return Response({
            'message': 'User registered successfully. Please verify your email.',
            'user': UserDetailSerializer(user).data
        }, status=status.HTTP_201_CREATED)


class PasswordResetRequestView(generics.GenericAPIView):
    """View for requesting password reset."""
    
    serializer_class = PasswordResetRequestSerializer
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Send password reset email."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = (serializer.validated_data.get('email') or '').strip()

        # Avoid account enumeration: always return success, only send email if user exists.
        user = User.objects.filter(email__iexact=email).first()
        if user:
            token_generator = PasswordResetTokenGenerator()
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = token_generator.make_token(user)

            frontend = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000').rstrip('/')
            reset_link = f"{frontend}/reset-password?uid={uid}&token={token}"

            subject = "Reset your password"
            message = (
                "You requested a password reset.\n\n"
                f"Reset link: {reset_link}\n\n"
                "If you didn’t request this, you can ignore this email."
            )
            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@airtasker.com'),
                recipient_list=[user.email],
                fail_silently=True,
            )
        
        return Response({
            'message': 'If an account exists for that email, a password reset link has been sent.'
        }, status=status.HTTP_200_OK)


class PasswordResetConfirmView(generics.GenericAPIView):
    """View for confirming password reset."""
    
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Reset password with token."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        uid = serializer.validated_data['uid']
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
        except Exception:
            return Response({'error': 'Invalid reset link.'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(pk=user_id).first()
        if not user:
            return Response({'error': 'Invalid reset link.'}, status=status.HTTP_400_BAD_REQUEST)

        token_generator = PasswordResetTokenGenerator()
        if not token_generator.check_token(user, token):
            return Response({'error': 'Reset token is invalid or expired.'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save(update_fields=['password'])
        
        return Response({
            'message': 'Password reset successfully.'
        }, status=status.HTTP_200_OK)


class EmailVerificationView(generics.GenericAPIView):
    """View for email verification."""
    
    serializer_class = EmailVerificationSerializer
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Verify email with token."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # TODO: Validate token and verify email
        
        return Response({
            'message': 'Email verified successfully.'
        }, status=status.HTTP_200_OK)
