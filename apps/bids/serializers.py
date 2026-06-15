"""
Serializers for Bid models.
"""
from rest_framework import serializers
from django.utils import timezone
from .models import Bid, BidMessage, BidReview, BidNotification
from apps.users.serializers import UserListSerializer
from apps.tasks.serializers import TaskListSerializer, TaskOwnerEmployerMixin
from apps.tasks.listing import get_listing_kind


class BidMessageSerializer(serializers.ModelSerializer):
    """Serializer for bid messages."""
    
    sender_name = serializers.CharField(source='sender.get_full_name', read_only=True)
    sender_image = serializers.URLField(source='sender.profile_image', read_only=True)
    
    class Meta:
        model = BidMessage
        fields = [
            'id', 'bid', 'message', 'sender', 'sender_name', 'sender_image',
            'is_read', 'read_at', 'created_at'
        ]
        read_only_fields = ['id', 'sender', 'is_read', 'read_at', 'created_at']


class BidReviewSerializer(serializers.ModelSerializer):
    """Serializer for bid reviews."""
    
    reviewer_name = serializers.CharField(source='reviewer.get_full_name', read_only=True)
    
    class Meta:
        model = BidReview
        fields = ['id', 'rating', 'comment', 'reviewer', 'reviewer_name', 'created_at']
        read_only_fields = ['id', 'reviewer', 'created_at']


class BidListSerializer(TaskOwnerEmployerMixin, serializers.ModelSerializer):
    """Lightweight serializer for bid lists."""
    
    tasker = UserListSerializer(read_only=True)
    task_title = serializers.CharField(source='task.title', read_only=True)
    task_slug = serializers.CharField(source='task.slug', read_only=True)
    task_city = serializers.CharField(source='task.city', read_only=True, allow_blank=True)
    task_listing_kind = serializers.SerializerMethodField()
    task_owner_logo_url = serializers.SerializerMethodField()
    task_owner_logo_text = serializers.SerializerMethodField()
    task_owner_logo_color = serializers.SerializerMethodField()
    task_owner_business_name = serializers.SerializerMethodField()
    task_owner_name = serializers.SerializerMethodField()
    is_pending = serializers.BooleanField(read_only=True)
    is_accepted = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Bid
        fields = [
            'id', 'task', 'task_title', 'task_slug', 'task_city', 'task_listing_kind', 'tasker',
            'task_owner_logo_url', 'task_owner_logo_text', 'task_owner_logo_color',
            'task_owner_business_name', 'task_owner_name',
            'amount', 'currency',
            'proposal', 'estimated_duration', 'estimated_completion_date',
            'status', 'is_pending', 'is_accepted', 'is_counter_offer',
            'created_at'
        ]
        read_only_fields = ['id', 'tasker', 'status', 'created_at']

    def get_task_listing_kind(self, obj):
        return get_listing_kind(obj.task.tags)

    def get_task_owner_logo_url(self, obj):
        return self.get_owner_logo_url(obj.task)

    def get_task_owner_logo_text(self, obj):
        return self.get_owner_logo_text(obj.task)

    def get_task_owner_logo_color(self, obj):
        return self.get_owner_logo_color(obj.task)

    def get_task_owner_business_name(self, obj):
        return self.get_owner_business_name(obj.task)

    def get_task_owner_name(self, obj):
        return self.get_owner_display_name(obj.task)


class BidDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for bid details."""
    
    tasker = UserListSerializer(read_only=True)
    task = TaskListSerializer(read_only=True)
    task_title = serializers.CharField(source='task.title', read_only=True)
    task_slug = serializers.CharField(source='task.slug', read_only=True)
    task_listing_kind = serializers.SerializerMethodField()
    messages = BidMessageSerializer(many=True, read_only=True)
    review = BidReviewSerializer(read_only=True)
    counter_offers = serializers.SerializerMethodField()
    is_pending = serializers.BooleanField(read_only=True)
    is_accepted = serializers.BooleanField(read_only=True)
    is_rejected = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Bid
        fields = [
            'id', 'task', 'task_title', 'task_slug', 'task_listing_kind', 'tasker',
            'amount', 'currency', 'proposal', 'cover_letter', 'estimated_duration',
            'estimated_completion_date', 'status', 'attachments',
            'is_counter_offer', 'original_bid', 'counter_offers',
            'rejection_reason', 'withdrawal_reason',
            'is_pending', 'is_accepted', 'is_rejected',
            'messages', 'review', 'created_at', 'updated_at',
            'accepted_at', 'rejected_at', 'withdrawn_at'
        ]
        read_only_fields = [
            'id', 'tasker', 'status', 'rejection_reason', 'withdrawal_reason',
            'created_at', 'updated_at', 'accepted_at', 'rejected_at', 'withdrawn_at'
        ]
    
    def get_counter_offers(self, obj):
        """Get counter offers for this bid."""
        if obj.counter_offers.exists():
            return BidListSerializer(obj.counter_offers.all(), many=True).data
        return []

    def get_task_listing_kind(self, obj):
        return get_listing_kind(obj.task.tags)


class BidCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating bids."""
    
    class Meta:
        model = Bid
        fields = [
            'task', 'amount', 'currency', 'proposal', 'cover_letter',
            'estimated_duration', 'estimated_completion_date', 'attachments'
        ]
    
    def validate_amount(self, value):
        """Validate bid amount."""
        if value <= 0:
            raise serializers.ValidationError("Bid amount must be greater than 0.")
        return value
    
    def validate_task(self, value):
        """Validate task can receive bids."""
        if value.status != 'open':
            raise serializers.ValidationError("Task is not open for bids.")
        
        if not value.allow_bids:
            raise serializers.ValidationError("This task does not allow bids.")
        
        if value.owner == self.context['request'].user:
            raise serializers.ValidationError("Cannot bid on your own task.")
        
        return value
    
    def validate(self, attrs):
        """Additional validation."""
        task = attrs['task']
        tasker = self.context['request'].user
        
        # Check if tasker already has a pending bid
        existing_bid = Bid.objects.filter(
            task=task,
            tasker=tasker,
            status='pending'
        ).first()
        
        if existing_bid:
            raise serializers.ValidationError({
                'non_field_errors': ['You already have a pending bid on this task. Please withdraw your existing bid first if you want to submit a new one.']
            })
        
        # Check if tasker has any bid (including non-pending) due to unique constraint
        any_existing_bid = Bid.objects.filter(
            task=task,
            tasker=tasker
        ).first()
        
        if any_existing_bid:
            raise serializers.ValidationError({
                'non_field_errors': [f'You already have a {any_existing_bid.status} bid on this task. Only one bid per task is allowed.']
            })
        
        return attrs
    
    def create(self, validated_data):
        """Create bid."""
        validated_data.setdefault('currency', 'NPR')
        validated_data['tasker'] = self.context['request'].user
        return super().create(validated_data)


class BidUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating bids."""
    
    class Meta:
        model = Bid
        fields = [
            'amount', 'proposal', 'cover_letter', 'estimated_duration',
            'estimated_completion_date', 'attachments'
        ]
    
    def validate(self, attrs):
        """Validate bid can be updated."""
        bid = self.instance
        if bid.status != 'pending':
            raise serializers.ValidationError(
                "Only pending bids can be updated."
            )
        return attrs


class BidAcceptSerializer(serializers.Serializer):
    """Serializer for accepting bids."""
    
    pass  # No additional fields needed


class BidRejectSerializer(serializers.Serializer):
    """Serializer for rejecting bids."""
    
    reason = serializers.CharField(required=False, allow_blank=True)


class BidWithdrawSerializer(serializers.Serializer):
    """Serializer for withdrawing bids."""
    
    reason = serializers.CharField(required=False, allow_blank=True)


class CounterOfferSerializer(serializers.Serializer):
    """Serializer for creating counter offers."""
    
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    proposal = serializers.CharField()
    
    def validate_amount(self, value):
        """Validate counter offer amount."""
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0.")
        return value


class BidNotificationSerializer(serializers.ModelSerializer):
    """Serializer for bid notifications."""
    
    bid_details = BidListSerializer(source='bid', read_only=True)
    
    class Meta:
        model = BidNotification
        fields = [
            'id', 'notification_type', 'message', 'bid', 'bid_details',
            'is_read', 'read_at', 'created_at'
        ]
        read_only_fields = ['id', 'is_read', 'read_at', 'created_at']


class BidStatsSerializer(serializers.Serializer):
    """Serializer for bid statistics."""
    
    total_bids = serializers.IntegerField()
    pending_bids = serializers.IntegerField()
    accepted_bids = serializers.IntegerField()
    rejected_bids = serializers.IntegerField()
    withdrawn_bids = serializers.IntegerField()
    average_bid_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_bid_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    acceptance_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
