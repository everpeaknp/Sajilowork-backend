"""
Serializers for Task models.
"""
from decimal import Decimal

from rest_framework import serializers
from django.utils.text import slugify
from .models import (
    Task, Category, TaskAttachment, TaskBookmark,
    TaskView, TaskQuestion, TaskReport
)
from apps.users.employer_profile_service import resolve_employer_image_url
from apps.users.user_media_utils import resolve_user_media_url

from .listing import (
    LISTING_KIND_CHOICES,
    LISTING_KIND_JOB,
    LISTING_KIND_TASK,
    LISTING_KIND_CATEGORY_CHOICES,
    get_listing_kind,
    with_listing_kind,
)
from apps.users.serializers import UserListSerializer


def _cover_attachment(task):
    """First uploaded attachment — used as the listing cover image."""
    prefetched = getattr(task, '_prefetched_objects_cache', {}).get('attachments')
    if prefetched is not None:
        if not prefetched:
            return None
        return min(prefetched, key=lambda item: item.uploaded_at)
    return task.attachments.order_by('uploaded_at').first()


def _resolve_cover_image_url(task, request=None):
    """Cover image URL from attachments only (no placeholder)."""
    attachment = _cover_attachment(task)
    if attachment and attachment.file_url:
        url = str(attachment.file_url).strip()
        if not url:
            return None
        if request and url.startswith('/'):
            return request.build_absolute_uri(url)
        return url
    return None


def _resolve_primary_image_url(task, request=None):
    """Cover image URL from attachments, or a stable stock placeholder."""
    attachment = _cover_attachment(task)
    if attachment and attachment.file_url:
        url = str(attachment.file_url).strip()
        if url and request and url.startswith('/'):
            return request.build_absolute_uri(url)
        if url:
            return url
    seed = task.slug or str(task.pk)
    return f'https://picsum.photos/seed/{seed}/800/600'


def _ordered_attachments(task):
    """Attachments in upload order (cover image first)."""
    prefetched = getattr(task, '_prefetched_objects_cache', {}).get('attachments')
    if prefetched is not None:
        return sorted(prefetched, key=lambda item: item.uploaded_at)
    return task.attachments.order_by('uploaded_at')


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for categories."""
    
    subcategories = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'description', 'icon',
            'listing_kind', 'parent', 'is_active', 'order', 'subcategories'
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


def _resolve_user_profile_image_url(user, request=None):
    return resolve_user_media_url(request, getattr(user, 'profile_image', None) if user else None)


class TaskQuestionSerializer(serializers.ModelSerializer):
    """Serializer for task questions."""

    asked_by_name = serializers.SerializerMethodField()
    asked_by_image = serializers.SerializerMethodField()
    is_answered = serializers.BooleanField(read_only=True)

    class Meta:
        model = TaskQuestion
        fields = [
            'id', 'question', 'answer', 'asked_by', 'asked_by_name',
            'asked_by_image', 'is_answered', 'is_public',
            'created_at', 'answered_at',
        ]
        read_only_fields = ['id', 'asked_by', 'answered_at', 'created_at']

    def get_asked_by_name(self, obj):
        asked_by = getattr(obj, 'asked_by', None)
        if not asked_by:
            return 'User'
        return asked_by.get_full_name() or getattr(asked_by, 'username', None) or 'User'

    def get_asked_by_image(self, obj):
        return _resolve_user_profile_image_url(
            getattr(obj, 'asked_by', None),
            self.context.get('request'),
        )

    def validate_question(self, value):
        trimmed = (value or '').strip()
        if not trimmed:
            raise serializers.ValidationError('Question cannot be empty.')
        return trimmed


def serialize_listing_questions(task, request):
    """Public users see only public questions; owners see all."""
    queryset = task.questions.select_related('asked_by').order_by('-created_at')
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or task.owner_id != user.id:
        queryset = queryset.filter(is_public=True)
    return TaskQuestionSerializer(
        queryset,
        many=True,
        context={'request': request},
    ).data


class DashboardTaskQuestionSerializer(serializers.ModelSerializer):
    """Task question with listing context for dashboard inbox."""

    asked_by_name = serializers.CharField(source='asked_by.get_full_name', read_only=True)
    asked_by_image = serializers.SerializerMethodField()
    task_id = serializers.UUIDField(source='task.id', read_only=True)
    task_title = serializers.CharField(source='task.title', read_only=True)
    task_slug = serializers.CharField(source='task.slug', read_only=True)
    task_listing_kind = serializers.SerializerMethodField()
    can_answer = serializers.SerializerMethodField()
    is_answered = serializers.BooleanField(read_only=True)

    class Meta:
        model = TaskQuestion
        fields = [
            'id', 'question', 'answer', 'asked_by', 'asked_by_name',
            'asked_by_image', 'is_answered', 'is_public',
            'created_at', 'answered_at',
            'task_id', 'task_title', 'task_slug', 'task_listing_kind', 'can_answer',
        ]
        read_only_fields = fields

    def get_asked_by_image(self, obj):
        asked_by = getattr(obj, 'asked_by', None)
        return _resolve_user_profile_image_url(asked_by, self.context.get('request'))

    def get_task_listing_kind(self, obj):
        kind = get_listing_kind(getattr(obj.task, 'tags', None))
        return kind or LISTING_KIND_TASK

    def get_can_answer(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.task.owner_id == request.user.id


def _get_owner_employer_profile(task):
    owner = getattr(task, 'owner', None)
    if not owner:
        return None
    return getattr(owner, 'employer_profile', None)


def _resolve_owner_personal_name(owner):
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


class TaskOwnerEmployerMixin:
    """Business profile fields for task owners (employer accounts)."""

    def get_owner_logo_url(self, obj):
        profile = _get_owner_employer_profile(obj)
        if profile and profile.logo_image:
            request = self.context.get('request')
            return resolve_employer_image_url(request, profile.logo_image)
        owner = getattr(obj, 'owner', None)
        return _resolve_user_profile_image_url(owner, self.context.get('request'))

    def get_owner_display_name(self, obj):
        profile = _get_owner_employer_profile(obj)
        if profile and profile.company_name.strip():
            return profile.company_name.strip()
        return _resolve_owner_personal_name(getattr(obj, 'owner', None))

    def get_owner_logo_text(self, obj):
        profile = _get_owner_employer_profile(obj)
        if profile and profile.logo_text.strip():
            return profile.logo_text.strip()
        owner = getattr(obj, 'owner', None)
        company_name = profile.company_name.strip() if profile and profile.company_name else ''
        seed = company_name or _resolve_owner_personal_name(owner)
        parts = seed.split()
        if len(parts) >= 2:
            return ''.join(part[0] for part in parts[:2]).upper()
        return (seed[:2] or 'CO').upper()

    def get_owner_logo_color(self, obj):
        profile = _get_owner_employer_profile(obj)
        if profile and profile.logo_color:
            return profile.logo_color
        return 'serif-m'

    def get_owner_business_name(self, obj):
        profile = _get_owner_employer_profile(obj)
        if profile and profile.company_name.strip():
            return profile.company_name.strip()
        return ''


class TaskListSerializer(TaskOwnerEmployerMixin, serializers.ModelSerializer):
    """Lightweight serializer for task lists."""
    
    owner_name = serializers.SerializerMethodField()
    owner_username = serializers.SerializerMethodField()
    owner_image = serializers.SerializerMethodField()
    owner_logo_url = serializers.SerializerMethodField()
    owner_logo_text = serializers.SerializerMethodField()
    owner_logo_color = serializers.SerializerMethodField()
    owner_business_name = serializers.SerializerMethodField()
    owner_rating = serializers.DecimalField(
        source='owner.average_rating',
        max_digits=3,
        decimal_places=2,
        read_only=True
    )
    owner_is_verified = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='category.name', read_only=True)
    listing_kind = serializers.SerializerMethodField()
    primary_image = serializers.SerializerMethodField()
    is_open = serializers.BooleanField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    is_bookmarked = serializers.SerializerMethodField()

    def get_is_bookmarked(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        bookmark_ids = self.context.get('user_bookmark_task_ids')
        if bookmark_ids is not None:
            return obj.pk in bookmark_ids
        return TaskBookmark.objects.filter(user=request.user, task=obj).exists()

    def get_listing_kind(self, obj):
        kind = get_listing_kind(obj.tags)
        return kind or LISTING_KIND_TASK

    def get_primary_image(self, obj):
        return _resolve_primary_image_url(obj, self.context.get('request'))

    def get_owner_name(self, obj):
        """
        Display name for the task poster on marketplace listings.
        Prefer employer business profile company name over personal name.
        """
        business_name = self.get_owner_business_name(obj)
        if business_name:
            return business_name
        return _resolve_owner_personal_name(getattr(obj, 'owner', None))
    
    def get_owner_username(self, obj):
        owner = getattr(obj, 'owner', None)
        if not owner:
            return ''
        return (getattr(owner, 'username', None) or '').strip()
    
    def get_owner_image(self, obj):
        """
        Return an absolute URL for the owner's profile image, or None.
        ImageField needs .url + build_absolute_uri; URLField(source=...) does
        not call .url on ImageFieldFile, which is why this used to break.
        """
        owner = getattr(obj, 'owner', None)
        return _resolve_user_profile_image_url(owner, self.context.get('request'))

    def get_owner_is_verified(self, obj):
        owner = getattr(obj, 'owner', None)
        return bool(owner and getattr(owner, 'is_verified_tasker', False))
    
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
            'category', 'category_name', 'listing_kind', 'tags', 'primary_image', 'owner', 'owner_name',
            'owner_username', 'owner_image', 'owner_logo_url', 'owner_logo_text', 'owner_logo_color',
            'owner_business_name', 'owner_rating', 'owner_is_verified', 'assigned_tasker', 'due_date',
            'is_public', 'is_open', 'is_overdue', 'is_bookmarked', 'views_count', 'bids_count', 'created_at'
        ]
        read_only_fields = [
            'id', 'slug', 'owner', 'views_count', 'bids_count', 'created_at'
        ]


class TaskDetailSerializer(TaskOwnerEmployerMixin, serializers.ModelSerializer):
    """Detailed serializer for task details."""
    
    owner = UserListSerializer(read_only=True)
    assigned_tasker = UserListSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    owner_name = serializers.SerializerMethodField()
    owner_username = serializers.SerializerMethodField()
    owner_image = serializers.SerializerMethodField()
    owner_logo_url = serializers.SerializerMethodField()
    owner_logo_text = serializers.SerializerMethodField()
    owner_logo_color = serializers.SerializerMethodField()
    owner_business_name = serializers.SerializerMethodField()
    owner_rating = serializers.DecimalField(
        source='owner.average_rating',
        max_digits=3,
        decimal_places=2,
        read_only=True,
    )
    owner_is_verified = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='category.name', read_only=True)
    primary_image = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()
    questions = serializers.SerializerMethodField()
    is_open = serializers.BooleanField(read_only=True)
    is_completed = serializers.BooleanField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    full_address = serializers.CharField(read_only=True)
    is_bookmarked = serializers.SerializerMethodField()
    listing_kind = serializers.SerializerMethodField()

    def get_listing_kind(self, obj):
        kind = get_listing_kind(obj.tags)
        return kind or LISTING_KIND_TASK

    def get_primary_image(self, obj):
        return _resolve_primary_image_url(obj, self.context.get('request'))

    def get_owner_name(self, obj):
        business_name = self.get_owner_business_name(obj)
        if business_name:
            return business_name
        return _resolve_owner_personal_name(getattr(obj, 'owner', None))

    def get_owner_username(self, obj):
        owner = getattr(obj, 'owner', None)
        if not owner:
            return ''
        return (getattr(owner, 'username', None) or '').strip()

    def get_owner_image(self, obj):
        owner = getattr(obj, 'owner', None)
        return _resolve_user_profile_image_url(owner, self.context.get('request'))

    def get_owner_is_verified(self, obj):
        owner = getattr(obj, 'owner', None)
        return bool(owner and getattr(owner, 'is_verified_tasker', False))

    def get_attachments(self, obj):
        ordered = _ordered_attachments(obj)
        return TaskAttachmentSerializer(ordered, many=True, context=self.context).data

    def get_questions(self, obj):
        return serialize_listing_questions(obj, self.context.get('request'))
    
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'slug', 'description', 'status', 'work_type', 'urgency',
            'budget_type', 'budget_amount', 'budget_currency',
            'location_type', 'address', 'city', 'state', 'country',
            'postal_code', 'latitude', 'longitude', 'full_address',
            'due_date', 'start_date', 'completion_date',
            'tasker_marked_complete_at', 'owner_marked_complete_at',
            'category', 'category_name', 'owner', 'owner_name', 'owner_username', 'owner_image',
            'owner_logo_url', 'owner_logo_text', 'owner_logo_color', 'owner_business_name',
            'owner_rating', 'owner_is_verified', 'primary_image',
            'assigned_tasker',
            'is_public', 'is_featured', 'allow_bids', 'auto_accept_bid',
            'views_count', 'bids_count', 'bookmarks_count',
            'tags', 'requirements', 'listing_kind', 'attachments', 'questions',
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

    listing_kind = serializers.ChoiceField(
        choices=LISTING_KIND_CATEGORY_CHOICES,
        required=False,
        allow_null=True,
        write_only=True,
    )
    
    class Meta:
        model = Task
        fields = [
            'id', 'slug', 'title', 'description', 'category', 'work_type', 'urgency',
            'budget_type', 'budget_amount', 'budget_currency',
            'location_type', 'address', 'city', 'state', 'country',
            'postal_code', 'latitude', 'longitude',
            'due_date', 'is_public', 'allow_bids', 'tags', 'requirements',
            'listing_kind',
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

    def validate(self, attrs):
        listing_kind = attrs.pop('listing_kind', None)
        request = self.context.get('request')
        user = getattr(request, 'user', None)

        if listing_kind and listing_kind != LISTING_KIND_TASK:
            if listing_kind == 'service':
                if user and user.role not in ('tasker', 'admin'):
                    raise serializers.ValidationError(
                        {'listing_kind': 'Only taskers can create service listings.'}
                    )
            elif listing_kind in ('project', 'job') and user and user.role == 'tasker':
                raise serializers.ValidationError(
                    {'listing_kind': 'Taskers cannot create project or job listings.'}
                )
            attrs['tags'] = with_listing_kind(attrs.get('tags'), listing_kind)

        return attrs
    
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
        elif task.status == 'open' and not task.allow_bids:
            task.allow_bids = True
            task.save(update_fields=['allow_bids'])
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

    def update(self, instance, validated_data):
        if 'tags' in validated_data:
            validated_data['tags'] = with_listing_kind(
                validated_data['tags'],
                get_listing_kind(instance.tags),
            )
        return super().update(instance, validated_data)


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
            'open': ['assigned', 'cancelled', 'completed'],
            'assigned': ['in_progress', 'open', 'cancelled'],
            'funded': ['in_progress', 'cancelled'],
            'in_progress': ['disputed', 'cancelled'],
            'pending_approval': ['in_progress', 'disputed', 'cancelled'],
            'completed': [],
            'cancelled': [],
            'disputed': ['in_progress', 'cancelled'],
        }
        
        allowed = list(valid_transitions.get(current_status, []))
        is_job_listing = get_listing_kind(task.tags) == LISTING_KIND_JOB
        if (
            is_job_listing
            and value == 'completed'
            and current_status in ('assigned', 'in_progress', 'funded')
        ):
            if value not in allowed:
                allowed.append(value)

        if value not in allowed:
            raise serializers.ValidationError(
                f"Cannot transition from {current_status} to {value}."
            )

        if value == 'completed' and current_status == 'open' and task.assigned_tasker_id:
            raise serializers.ValidationError(
                'Cannot mark as completed while a freelancer is assigned. '
                'Confirm completion after work is in progress.'
            )

        if value == 'completed' and current_status == 'open':
            if task.bids.filter(status='pending').exists():
                raise serializers.ValidationError(
                    'Cannot mark as completed while proposals are still pending. '
                    'Accept or reject them first.'
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
        read_only_fields = ['id', 'task', 'reported_by', 'status', 'created_at']


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
