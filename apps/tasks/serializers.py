"""
Serializers for Task models.
"""
from rest_framework import serializers
from django.utils.text import slugify
from .models import (
    Task, Category, TaskAttachment, TaskBookmark,
    TaskView, TaskQuestion, TaskReport
)
from apps.users.serializers import UserListSerializer


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for categories."""
    
    subcategories = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'description', 'icon',
            'parent', 'is_active', 'order', 'subcategories'
        ]
        read_only_fields = ['id']
    
    def get_subcategories(self, obj):
        """Get subcategories if this is a parent category."""
        if obj.subcategories.exists():
            return CategorySerializer(obj.subcategories.all(), many=True).data
        return []


class TaskAttachmentSerializer(serializers.ModelSerializer):
    """Serializer for task attachments."""
    
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    
    class Meta:
        model = TaskAttachment
        fields = [
            'id', 'file_url', 'file_name', 'file_type', 'file_size',
            'uploaded_by', 'uploaded_by_name', 'uploaded_at'
        ]
        read_only_fields = ['id', 'uploaded_by', 'uploaded_at']


class TaskQuestionSerializer(serializers.ModelSerializer):
    """Serializer for task questions."""
    
    asked_by_name = serializers.CharField(source='asked_by.get_full_name', read_only=True)
    asked_by_image = serializers.URLField(source='asked_by.profile_image', read_only=True)
    is_answered = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = TaskQuestion
        fields = [
            'id', 'question', 'answer', 'asked_by', 'asked_by_name',
            'asked_by_image', 'is_answered', 'is_public',
            'created_at', 'answered_at'
        ]
        read_only_fields = ['id', 'asked_by', 'answered_at', 'created_at']


class TaskListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for task lists."""
    
    owner_name = serializers.SerializerMethodField()
    owner_image = serializers.SerializerMethodField()
    owner_rating = serializers.DecimalField(
        source='owner.average_rating',
        max_digits=3,
        decimal_places=2,
        read_only=True
    )
    category_name = serializers.CharField(source='category.name', read_only=True)
    is_open = serializers.BooleanField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    
    def get_owner_name(self, obj):
        """
        Best-effort display name for the task poster.
        Falls back through full name -> username -> email local-part
        so the UI never has to render an empty "Unknown".
        """
        owner = getattr(obj, 'owner', None)
        if not owner:
            return ''
        full = (owner.get_full_name() or '').strip()
        if full:
            return full
        if getattr(owner, 'username', None):
            return owner.username
        if getattr(owner, 'email', None):
            return owner.email.split('@')[0]
        return ''
    
    def get_owner_image(self, obj):
        """
        Return an absolute URL for the owner's profile image, or None.
        ImageField needs .url + build_absolute_uri; URLField(source=...) does
        not call .url on ImageFieldFile, which is why this used to break.
        """
        owner = getattr(obj, 'owner', None)
        if not owner or not getattr(owner, 'profile_image', None):
            return None
        try:
            url = owner.profile_image.url
        except (ValueError, AttributeError):
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(url)
        return url
    
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'slug', 'description', 'status', 'work_type',
            'budget_type', 'budget_amount', 'budget_currency',
            'location_type', 'address', 'city', 'state', 'country',
            # latitude/longitude are needed so the /task map view can render
            # pins for each task. Without them every task falls back to the
            # frontend's default fallback coordinates.
            'latitude', 'longitude',
            'category', 'category_name', 'owner', 'owner_name',
            'owner_image', 'owner_rating', 'assigned_tasker', 'due_date',
            'is_open', 'is_overdue', 'views_count', 'bids_count', 'created_at'
        ]
        read_only_fields = [
            'id', 'slug', 'owner', 'views_count', 'bids_count', 'created_at'
        ]


class TaskDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for task details."""
    
    owner = UserListSerializer(read_only=True)
    assigned_tasker = UserListSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    attachments = TaskAttachmentSerializer(many=True, read_only=True)
    questions = TaskQuestionSerializer(many=True, read_only=True)
    is_open = serializers.BooleanField(read_only=True)
    is_completed = serializers.BooleanField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    full_address = serializers.CharField(read_only=True)
    is_bookmarked = serializers.SerializerMethodField()
    
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'slug', 'description', 'status', 'work_type', 'urgency',
            'budget_type', 'budget_amount', 'budget_currency',
            'location_type', 'address', 'city', 'state', 'country',
            'postal_code', 'latitude', 'longitude', 'full_address',
            'due_date', 'start_date', 'completion_date',
            'tasker_marked_complete_at', 'owner_marked_complete_at',
            'category', 'owner', 'assigned_tasker',
            'is_public', 'is_featured', 'allow_bids', 'auto_accept_bid',
            'views_count', 'bids_count', 'bookmarks_count',
            'tags', 'requirements', 'attachments', 'questions',
            'is_open', 'is_completed', 'is_overdue', 'is_bookmarked',
            'created_at', 'updated_at', 'published_at'
        ]
        read_only_fields = [
            'id', 'slug', 'owner', 'assigned_tasker', 'status',
            'views_count', 'bids_count', 'bookmarks_count',
            'start_date', 'completion_date', 'created_at',
            'updated_at', 'published_at'
        ]
    
    def get_is_bookmarked(self, obj):
        """Check if current user has bookmarked this task."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return TaskBookmark.objects.filter(user=request.user, task=obj).exists()
        return False


class TaskCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating tasks."""
    
    class Meta:
        model = Task
        fields = [
            'id', 'slug', 'title', 'description', 'category', 'work_type', 'urgency',
            'budget_type', 'budget_amount', 'budget_currency',
            'location_type', 'address', 'city', 'state', 'country',
            'postal_code', 'latitude', 'longitude',
            'due_date', 'is_public', 'allow_bids', 'tags', 'requirements',
            'status', 'created_at'
        ]
        read_only_fields = ['id', 'slug', 'status', 'created_at']
        extra_kwargs = {
            'category': {'required': False, 'allow_null': True},
            'urgency': {'required': False},
            'work_type': {'required': False},
            'location_type': {'required': False},
        }
    
    def validate_budget_amount(self, value):
        """Validate budget amount."""
        if value <= 0:
            raise serializers.ValidationError("Budget amount must be greater than 0.")

        # Admin-configured min/max (stored in rules)
        try:
            from apps.rules.models import RuleCategory
            from apps.rules.policy_store import get_active_policy_parameters

            params = get_active_policy_parameters(RuleCategory.OFFER, "task_budget_limits")
            min_raw = params.get("min_budget_npr")
            max_raw = params.get("max_budget_npr")
            if min_raw is not None and value < Decimal(str(min_raw)):
                raise serializers.ValidationError(f"Minimum budget is NPR {min_raw}.")
            if max_raw is not None and value > Decimal(str(max_raw)):
                raise serializers.ValidationError(f"Maximum budget is NPR {max_raw}.")
        except serializers.ValidationError:
            raise
        except Exception:
            # Never break task posting if the policy record is missing/misconfigured.
            pass

        return value
    
    def create(self, validated_data):
        """Create task with owner; auto-geocode if coords are missing."""
        validated_data['owner'] = self.context['request'].user
        if not validated_data.get('budget_currency'):
            validated_data['budget_currency'] = 'NPR'
        if validated_data.get('location_type', 'physical') != 'remote' and not validated_data.get('country'):
            validated_data['country'] = 'Nepal'

        # Safety net: if the client posted an address/city but failed to
        # supply coordinates (e.g. browser geolocation denied, OSM lookup
        # silently failed), do a server-side Nominatim lookup so the task
        # always renders on the map.
        needs_geocode = (
            validated_data.get('location_type', 'physical') != 'remote'
            and (validated_data.get('latitude') is None
                 or validated_data.get('longitude') is None)
            and (validated_data.get('address') or validated_data.get('city'))
        )
        if needs_geocode:
            from .geocoding import geocode_location  # local import avoids cycle

            parts = [
                validated_data.get('address') or '',
                validated_data.get('city') or '',
                validated_data.get('state') or '',
                validated_data.get('country') or 'Nepal',
            ]
            query = ", ".join(p.strip() for p in parts if p and p.strip())
            result = geocode_location(query)
            if result:
                validated_data['latitude'], validated_data['longitude'] = result

        task = super().create(validated_data)
        # Post-task flow submits a finished task — publish immediately so it
        # appears as a live "Posted" task, not a draft in "Booking requests".
        if task.status == 'draft':
            task.publish()
        return task


class TaskUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating tasks."""
    
    class Meta:
        model = Task
        fields = [
            'title', 'description', 'category', 'work_type', 'urgency',
            'budget_type', 'budget_amount', 'budget_currency',
            'location_type', 'address', 'city', 'state', 'country',
            'postal_code', 'latitude', 'longitude',
            'due_date', 'is_public', 'allow_bids', 'tags', 'requirements'
        ]
    
    def validate(self, attrs):
        """Validate that task can be updated."""
        task = self.instance
        if task.status not in ['draft', 'open']:
            raise serializers.ValidationError(
                "Cannot update task that is already assigned or completed."
            )
        return attrs


class TaskStatusSerializer(serializers.Serializer):
    """Serializer for updating task status."""
    
    status = serializers.ChoiceField(choices=Task.STATUS_CHOICES)
    
    def validate_status(self, value):
        """Validate status transition."""
        task = self.context['task']
        current_status = task.status
        
        # Define valid status transitions
        valid_transitions = {
            'draft': ['open', 'cancelled'],
            'open': ['assigned', 'cancelled'],
            'assigned': ['in_progress', 'open', 'cancelled'],
            'funded': ['in_progress', 'cancelled'],
            'in_progress': ['disputed', 'cancelled'],
            'pending_approval': ['in_progress', 'disputed', 'cancelled'],
            'completed': [],
            'cancelled': [],
            'disputed': ['in_progress', 'cancelled'],
        }
        
        if value not in valid_transitions.get(current_status, []):
            raise serializers.ValidationError(
                f"Cannot transition from {current_status} to {value}."
            )
        
        return value


class TaskBookmarkSerializer(serializers.ModelSerializer):
    """Serializer for task bookmarks."""
    
    task = TaskListSerializer(read_only=True)
    
    class Meta:
        model = TaskBookmark
        fields = ['id', 'task', 'created_at']
        read_only_fields = ['id', 'created_at']


class TaskReportSerializer(serializers.ModelSerializer):
    """Serializer for task reports."""
    
    reported_by_name = serializers.CharField(source='reported_by.get_full_name', read_only=True)
    
    class Meta:
        model = TaskReport
        fields = [
            'id', 'task', 'reason', 'description', 'status',
            'reported_by', 'reported_by_name', 'created_at'
        ]
        read_only_fields = ['id', 'reported_by', 'status', 'created_at']


class TaskStatsSerializer(serializers.Serializer):
    """Serializer for task statistics."""
    
    total_tasks = serializers.IntegerField()
    open_tasks = serializers.IntegerField()
    assigned_tasks = serializers.IntegerField()
    in_progress_tasks = serializers.IntegerField()
    completed_tasks = serializers.IntegerField()
    cancelled_tasks = serializers.IntegerField()
    total_budget = serializers.DecimalField(max_digits=10, decimal_places=2)
    average_budget = serializers.DecimalField(max_digits=10, decimal_places=2)
