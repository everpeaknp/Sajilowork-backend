"""Review API — bidirectional, server-enforced direction."""
from rest_framework import status, viewsets, mixins
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.shortcuts import get_object_or_404

from apps.users.models import User

from .models import Review, ReviewInvitation
from .serializers import (
    ReviewCreateSerializer,
    ReviewDetailSerializer,
    ReviewHelpfulVoteSerializer,
    ReviewInvitationSerializer,
    ReviewListSerializer,
    ReviewReportCreateSerializer,
    ReviewRespondSerializer,
    UserReviewStatsSerializer,
)
from .services import ReviewService


class ReviewCreateAPIView(APIView):
    """
    POST /api/v1/reviews/create/
    Body: { task_id, rating, comment?, tags? }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ReviewCreateSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        review = serializer.save()
        return Response(
            ReviewDetailSerializer(review, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class UserReviewsAPIView(APIView):
    """
    GET /api/v1/reviews/user/<user_id>/
    All published reviews received by that user.
    """

    permission_classes = [AllowAny]

    def get(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        reviews = ReviewService.get_reviews_received(user)
        stats = ReviewService.get_review_statistics(user)
        page = self.paginate_queryset(reviews) if hasattr(self, 'paginate_queryset') else None
        data = ReviewListSerializer(
            page if page is not None else reviews,
            many=True,
            context={'request': request},
        ).data
        return Response({
            'user_id': str(user.id),
            'statistics': UserReviewStatsSerializer(stats).data,
            'count': reviews.count(),
            'results': data,
        })


class ReviewViewSet(viewsets.ReadOnlyModelViewSet):
    """List/retrieve public reviews, and allow authenticated creation."""

    permission_classes = [AllowAny]
    serializer_class = ReviewListSerializer

    def get_queryset(self):
        return ReviewService.public_reviews_queryset().select_related(
            'task', 'reviewer', 'reviewee',
        ).prefetch_related('helpful_votes', 'reports')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ReviewDetailSerializer
        return ReviewListSerializer

    def get_permissions(self):
        if self.action in ['create', 'my_task_review_status']:
            return [IsAuthenticated()]
        return [AllowAny()]

    def create(self, request, *args, **kwargs):
        """
        POST /api/v1/reviews/
        Body: { task_id, rating, comment?, tags? }
        """
        serializer = ReviewCreateSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        review = serializer.save()
        return Response(
            ReviewDetailSerializer(review, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def eligible_tasks(self, request):
        """
        GET /api/v1/reviews/eligible_tasks/?reviewee_id=<uuid>
        Completed work with reviewee that the current user can still review.
        """
        reviewee_id = request.query_params.get('reviewee_id')
        if not reviewee_id:
            return Response(
                {'detail': 'reviewee_id is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tasks = ReviewService.get_reviewable_tasks_for_reviewee(request.user, reviewee_id)
        return Response([
            {'task_id': str(task.id), 'task_title': task.title or 'Completed work'}
            for task in tasks
        ])

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def pending_invitations(self, request):
        invitations = ReviewInvitation.objects.filter(
            invitee=request.user,
            status='pending',
            expires_at__gt=__import__('django').utils.timezone.now(),
        ).select_related('task', 'task__owner', 'task__assigned_tasker')
        return Response(
            ReviewInvitationSerializer(
                invitations, many=True, context={'request': request},
            ).data,
        )

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_task_review_status(self, request):
        """
        GET /api/v1/reviews/my_task_review_status/?task_id=<uuid>
        Returns whether the current user already reviewed this task.
        """
        task_id = request.query_params.get('task_id')
        if not task_id:
            return Response({'detail': 'task_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        review = Review.objects.filter(task_id=task_id, reviewer=request.user).only('id').first()
        return Response({'task_id': task_id, 'has_reviewed': bool(review), 'review_id': str(review.id) if review else None})

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_reviews(self, request):
        reviews = Review.objects.filter(reviewer=request.user).select_related(
            'task', 'reviewee',
        )
        return Response(
            ReviewListSerializer(
                reviews,
                many=True,
                context={'request': request},
            ).data,
        )

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def received(self, request):
        reviews = ReviewService.get_reviews_received(request.user)
        return Response(
            ReviewListSerializer(
                reviews,
                many=True,
                context={'request': request},
            ).data,
        )

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def stats(self, request):
        stats = ReviewService.get_review_statistics(request.user)
        return Response(UserReviewStatsSerializer(stats).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def respond(self, request, pk=None):
        review = get_object_or_404(Review, pk=pk)
        serializer = ReviewRespondSerializer(
            data=request.data,
            context={'request': request, 'review': review},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ReviewDetailSerializer(review).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated], url_path='helpful')
    def helpful(self, request, pk=None):
        review = get_object_or_404(
            ReviewService.public_reviews_queryset().prefetch_related('helpful_votes'),
            pk=pk,
        )
        serializer = ReviewHelpfulVoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vote_action = serializer.validated_data['vote']
        if vote_action == 'clear':
            review.helpful_votes.filter(user=request.user).delete()
        else:
            from .models import ReviewHelpful

            ReviewHelpful.objects.update_or_create(
                review=review,
                user=request.user,
                defaults={'is_helpful': vote_action == 'helpful'},
            )
        review = ReviewService.public_reviews_queryset().prefetch_related(
            'helpful_votes', 'reports',
        ).get(pk=pk)
        return Response(
            ReviewListSerializer(review, context={'request': request}).data,
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated], url_path='report')
    def report(self, request, pk=None):
        review = get_object_or_404(ReviewService.public_reviews_queryset(), pk=pk)
        serializer = ReviewReportCreateSerializer(
            data=request.data,
            context={'request': request, 'review': review},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': 'Review reported for moderation.'}, status=status.HTTP_201_CREATED)
