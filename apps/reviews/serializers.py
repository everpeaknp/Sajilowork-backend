"""Serializers for bidirectional reviews."""
from rest_framework import serializers

from apps.tasks.serializers import TaskListSerializer
from apps.users.serializers import PublicUserSerializer

from .models import Review, ReviewHelpful, ReviewReport, ReviewInvitation
from .services import ReviewService


class ReviewListSerializer(serializers.ModelSerializer):
    reviewer = PublicUserSerializer(read_only=True)
    reviewee = PublicUserSerializer(read_only=True)
    task_title = serializers.CharField(source='task.title', read_only=True)
    rating = serializers.IntegerField(source='overall_rating', read_only=True)
    comment = serializers.CharField(source='review_text', read_only=True)

    class Meta:
        model = Review
        fields = [
            'id',
            'task',
            'task_title',
            'reviewer',
            'reviewee',
            'reviewer_type',
            'review_type',
            'rating',
            'comment',
            'tags',
            'would_recommend',
            'is_verified',
            'response_text',
            'response_at',
            'created_at',
        ]
        read_only_fields = fields


class ReviewDetailSerializer(ReviewListSerializer):
    task = TaskListSerializer(read_only=True)

    class Meta(ReviewListSerializer.Meta):
        fields = ReviewListSerializer.Meta.fields + [
            'communication_rating',
            'quality_rating',
            'speed_rating',
            'professionalism_rating',
            'clarity_rating',
            'payment_experience_rating',
            'would_work_again',
            'is_public',
            'visible_at',
            'updated_at',
        ]


class ReviewCreateSerializer(serializers.Serializer):
    """
    POST /api/v1/reviews/create/
    Server assigns reviewee and reviewer_type — never accept them from client.
    """

    task_id = serializers.UUIDField()
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=5000)
    tags = serializers.ListField(
        child=serializers.CharField(max_length=64),
        required=False,
        allow_empty=True,
    )

    def create(self, validated_data):
        request = self.context['request']
        return ReviewService.create_review(
            task_id=validated_data['task_id'],
            reviewer=request.user,
            rating=validated_data['rating'],
            comment=validated_data.get('comment', ''),
            tags=validated_data.get('tags'),
            submitter_ip=request.META.get('REMOTE_ADDR'),
            submitter_user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )


class ReviewRespondSerializer(serializers.Serializer):
    response_text = serializers.CharField(max_length=2000)

    def validate(self, attrs):
        review = self.context['review']
        user = self.context['request'].user
        if user != review.reviewee:
            raise serializers.ValidationError('Only the reviewee can respond.')
        if review.response_text:
            raise serializers.ValidationError('This review already has a response.')
        if review.is_finalized and ReviewService.get_settings().edit_window_minutes == 0:
            pass
        return attrs

    def save(self):
        review = self.context['review']
        from django.utils import timezone

        review.response_text = self.validated_data['response_text']
        review.response_at = timezone.now()
        review.save(update_fields=['response_text', 'response_at', 'updated_at'])
        return review


class ReviewInvitationSerializer(serializers.ModelSerializer):
    task_title = serializers.CharField(source='task.title', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = ReviewInvitation
        fields = [
            'id',
            'task',
            'task_title',
            'reviewer_type',
            'status',
            'sent_at',
            'expires_at',
            'completed_at',
            'is_expired',
        ]
        read_only_fields = fields


class ReviewReportCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewReport
        fields = ['review', 'reason', 'description']

    def create(self, validated_data):
        validated_data['reporter'] = self.context['request'].user
        return super().create(validated_data)


class UserReviewStatsSerializer(serializers.Serializer):
    total_reviews = serializers.IntegerField()
    average_rating = serializers.FloatField(allow_null=True)
    rating_distribution = serializers.DictField(child=serializers.IntegerField())
    as_tasker_reviews = serializers.IntegerField()
    as_customer_reviews = serializers.IntegerField()
    trust_score = serializers.FloatField()
