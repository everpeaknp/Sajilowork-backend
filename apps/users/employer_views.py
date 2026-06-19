"""Employer profile API — dashboard editing and public pages."""
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.models import Project
from apps.projects.serializers import ProjectListSerializer
from apps.jobs.models import Job
from apps.jobs.serializers import JobListSerializer
from apps.reviews.serializers import ReviewListSerializer, UserReviewStatsSerializer
from apps.reviews.services import ReviewService

from .employer_profile_service import (
    ALLOWED_EMPLOYER_IMAGE_CONTENT_TYPES,
    MAX_EMPLOYER_GALLERY_BYTES,
    MAX_EMPLOYER_GALLERY_ITEMS,
    MAX_EMPLOYER_LOGO_BYTES,
    get_employer_user_by_slug,
    get_or_create_employer_profile,
    save_employer_gallery_upload,
    save_employer_logo_upload,
)
from apps.uploads.cloudinary_utils import is_cloudinary_url
from apps.users.user_media_utils import clear_stored_user_media
from .employer_serializers import (
    EmployerGalleryImageSerializer,
    EmployerMyProfileSerializer,
    EmployerProfileWriteSerializer,
    EmployerPublicProfileSerializer,
)
from .models import EmployerGalleryImage, EmployerProfile


class EmployerProfileMeView(APIView):
    """GET/PATCH /api/v1/users/me/employer-profile/"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'customer':
            return Response(
                {'error': 'Only employer accounts can manage a business profile.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        profile = get_or_create_employer_profile(request.user)
        profile = (
            EmployerProfile.objects.filter(pk=profile.pk)
            .select_related('user')
            .prefetch_related('gallery_images')
            .first()
        )
        serializer = EmployerMyProfileSerializer(profile, context={'request': request})
        return Response(serializer.data)

    def patch(self, request):
        if request.user.role != 'customer':
            return Response(
                {'error': 'Only employer accounts can manage a business profile.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        profile = get_or_create_employer_profile(request.user)
        serializer = EmployerProfileWriteSerializer(
            profile,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        profile = (
            EmployerProfile.objects.filter(pk=profile.pk)
            .select_related('user')
            .prefetch_related('gallery_images')
            .first()
        )
        output = EmployerMyProfileSerializer(profile, context={'request': request})
        return Response(output.data)


class EmployerLogoUploadView(APIView):
    """POST /api/v1/users/me/employer-profile/logo/"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != 'customer':
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        uploaded = request.FILES.get('file') or request.FILES.get('logo')
        image_url = (request.data.get('image_url') or request.data.get('cloudinary_url') or '').strip()

        if not uploaded and not image_url:
            return Response({'error': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        if image_url and not is_cloudinary_url(image_url):
            return Response(
                {'error': 'Invalid image URL. Only Cloudinary URLs are accepted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if uploaded:
            if uploaded.size > MAX_EMPLOYER_LOGO_BYTES:
                return Response({'error': 'Logo must be 1MB or smaller.'}, status=status.HTTP_400_BAD_REQUEST)
            content_type = (uploaded.content_type or '').lower()
            if content_type and content_type not in ALLOWED_EMPLOYER_IMAGE_CONTENT_TYPES:
                return Response(
                    {'error': 'Logo must be JPG, PNG, or WEBP.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        profile = get_or_create_employer_profile(request.user)
        clear_stored_user_media(profile.logo_image)

        try:
            if image_url:
                profile.logo_image = image_url
            else:
                profile.logo_image = save_employer_logo_upload(request.user, uploaded)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        profile.save(update_fields=['logo_image', 'updated_at'])

        output = EmployerMyProfileSerializer(profile, context={'request': request})
        return Response(output.data, status=status.HTTP_200_OK)


class EmployerGalleryListCreateView(APIView):
    """GET/POST /api/v1/users/me/employer-profile/gallery/"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = get_or_create_employer_profile(request.user)
        images = profile.gallery_images.all()
        serializer = EmployerGalleryImageSerializer(images, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        if request.user.role != 'customer':
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        profile = get_or_create_employer_profile(request.user)
        if profile.gallery_images.count() >= MAX_EMPLOYER_GALLERY_ITEMS:
            return Response(
                {'error': f'Maximum {MAX_EMPLOYER_GALLERY_ITEMS} gallery images allowed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        uploaded = request.FILES.get('file') or request.FILES.get('image')
        image_url = (request.data.get('image_url') or request.data.get('cloudinary_url') or '').strip()

        if not uploaded and not image_url:
            return Response({'error': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        if image_url and not is_cloudinary_url(image_url):
            return Response(
                {'error': 'Invalid image URL. Only Cloudinary URLs are accepted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if uploaded:
            if uploaded.size > MAX_EMPLOYER_GALLERY_BYTES:
                return Response(
                    {'error': 'Each gallery image must be 1MB or smaller.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            content_type = (uploaded.content_type or '').lower()
            if content_type and content_type not in ALLOWED_EMPLOYER_IMAGE_CONTENT_TYPES:
                return Response(
                    {'error': 'Gallery images must be JPG, PNG, or WEBP.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        alt_text = (request.data.get('alt_text') or request.data.get('alt') or '').strip()[:255]
        sort_order = profile.gallery_images.count()

        try:
            stored_url = image_url or save_employer_gallery_upload(request.user, uploaded)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        image = EmployerGalleryImage.objects.create(
            profile=profile,
            image=stored_url,
            alt_text=alt_text,
            sort_order=sort_order,
        )
        serializer = EmployerGalleryImageSerializer(image, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class EmployerGalleryDetailView(APIView):
    """DELETE /api/v1/users/me/employer-profile/gallery/<uuid:id>/"""

    permission_classes = [IsAuthenticated]

    def delete(self, request, id):
        profile = get_or_create_employer_profile(request.user)
        image = get_object_or_404(EmployerGalleryImage, pk=id, profile=profile)
        clear_stored_user_media(image.image)
        image.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EmployerDirectoryPagination(PageNumberPagination):
    page_size = 8
    page_size_query_param = 'page_size'
    max_page_size = 200


class EmployerPublicListView(APIView):
    """GET /api/v1/employers/ — public employer directory."""

    permission_classes = [AllowAny]

    def get(self, request):
        queryset = (
            EmployerProfile.objects.filter(
                is_public=True,
                user__is_active=True,
                user__account_suspended=False,
                user__role='customer',
            )
            .select_related('user')
            .prefetch_related('gallery_images')
        )

        search = (request.query_params.get('search') or '').strip()
        if search:
            queryset = queryset.filter(
                Q(company_name__icontains=search)
                | Q(industry__icontains=search)
                | Q(user__tagline__icontains=search)
                | Q(user__bio__icontains=search)
                | Q(user__city__icontains=search)
                | Q(user__username__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
            )

        industry = (request.query_params.get('industry') or '').strip()
        if industry and industry.lower() != 'all':
            if industry == 'Individual':
                queryset = queryset.filter(account_type='individual')
            else:
                queryset = queryset.filter(industry__iexact=industry)

        team_size = (request.query_params.get('team_size') or '').strip()
        if team_size and team_size.lower() != 'all':
            queryset = queryset.filter(team_size=team_size)

        ordering = (request.query_params.get('ordering') or 'best-seller').strip()
        if ordering == 'review-count':
            queryset = queryset.order_by('-user__total_reviews', '-user__average_rating', 'company_name')
        elif ordering == 'open-jobs':
            queryset = queryset.annotate(
                open_jobs_count=Count(
                    'user__posted_tasks',
                    filter=Q(
                        user__posted_tasks__is_public=True,
                        user__posted_tasks__status='open',
                        user__posted_tasks__tags__icontains='listing:job',
                    ),
                )
            ).order_by('-open_jobs_count', '-user__average_rating', 'company_name')
        else:
            queryset = queryset.order_by('-user__average_rating', '-user__total_reviews', 'company_name')

        paginator = EmployerDirectoryPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = EmployerPublicProfileSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class EmployerPublicDetailView(APIView):
    """GET /api/v1/employers/<slug>/"""

    permission_classes = [AllowAny]

    def get(self, request, slug):
        user = get_employer_user_by_slug(slug)
        if not user:
            return Response({'error': 'Employer not found.'}, status=status.HTTP_404_NOT_FOUND)

        profile = EmployerProfile.objects.filter(user=user).prefetch_related('gallery_images').first()
        if not profile:
            profile = get_or_create_employer_profile(user)
        elif not profile.is_public and request.user != user:
            return Response({'error': 'Employer not found.'}, status=status.HTTP_404_NOT_FOUND)

        if profile.pk:
            profile = (
                EmployerProfile.objects.filter(pk=profile.pk)
                .select_related('user')
                .prefetch_related('gallery_images')
                .first()
            )
        serializer = EmployerPublicProfileSerializer(profile, context={'request': request})
        return Response(serializer.data)


class EmployerPublicProjectsView(APIView):
    """GET /api/v1/employers/<slug>/projects/"""

    permission_classes = [AllowAny]

    def get(self, request, slug):
        user = get_employer_user_by_slug(slug)
        if not user:
            return Response({'error': 'Employer not found.'}, status=status.HTTP_404_NOT_FOUND)

        queryset = (
            Project.objects.filter(owner=user, is_public=True, status='open')
            .select_related('owner', 'owner__employer_profile', 'category')
            .order_by('-created_at')
        )
        serializer = ProjectListSerializer(queryset, many=True, context={'request': request})
        return Response({'count': queryset.count(), 'results': serializer.data})


class EmployerPublicJobsView(APIView):
    """GET /api/v1/employers/<slug>/jobs/"""

    permission_classes = [AllowAny]

    def get(self, request, slug):
        user = get_employer_user_by_slug(slug)
        if not user:
            return Response({'error': 'Employer not found.'}, status=status.HTTP_404_NOT_FOUND)

        queryset = (
            Job.objects.filter(owner=user, is_public=True, status='open')
            .select_related('owner', 'owner__employer_profile', 'category')
            .order_by('-created_at')
        )
        serializer = JobListSerializer(queryset, many=True, context={'request': request})
        return Response({'count': queryset.count(), 'results': serializer.data})


class EmployerPublicReviewsView(APIView):
    """GET /api/v1/employers/<slug>/reviews/"""

    permission_classes = [AllowAny]

    def get(self, request, slug):
        user = get_employer_user_by_slug(slug)
        if not user:
            return Response({'error': 'Employer not found.'}, status=status.HTTP_404_NOT_FOUND)

        reviews = ReviewService.get_reviews_received(user)
        stats = ReviewService.get_review_statistics(user)
        data = ReviewListSerializer(reviews, many=True, context={'request': request}).data
        return Response({
            'user_id': str(user.id),
            'statistics': UserReviewStatsSerializer(stats).data,
            'count': reviews.count(),
            'results': data,
        })
