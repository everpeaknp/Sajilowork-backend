"""
Search App Serializers
"""
from rest_framework import serializers
from django.db.models import Q
from apps.search.models import (
    SearchHistory, SavedSearch, PopularSearch,
    SearchSuggestion, SearchFilter
)
from apps.tasks.models import Task, Category
from apps.tasks.serializers import TaskOwnerEmployerMixin, _resolve_owner_personal_name
from apps.users.models import User


class SearchHistorySerializer(serializers.ModelSerializer):
    """Serializer for search history"""
    
    class Meta:
        model = SearchHistory
        fields = [
            'id', 'query', 'search_type', 'filters',
            'results_count', 'clicked_result', 'clicked_result_id',
            'clicked_result_type', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class SavedSearchSerializer(serializers.ModelSerializer):
    """Serializer for saved searches"""
    
    class Meta:
        model = SavedSearch
        fields = [
            'id', 'name', 'query', 'search_type', 'filters',
            'notify_new_results', 'notification_frequency',
            'last_notified_at', 'last_result_count', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'last_notified_at', 'last_result_count', 'created_at', 'updated_at']


class SavedSearchCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating saved searches"""
    
    class Meta:
        model = SavedSearch
        fields = [
            'name', 'query', 'search_type', 'filters',
            'notify_new_results', 'notification_frequency'
        ]


class PopularSearchSerializer(serializers.ModelSerializer):
    """Serializer for popular searches"""
    
    class Meta:
        model = PopularSearch
        fields = [
            'id', 'query', 'search_count', 'click_through_rate',
            'is_trending', 'last_searched_at'
        ]
        read_only_fields = ['id', 'search_count', 'click_through_rate', 'last_searched_at']


class SearchSuggestionSerializer(serializers.ModelSerializer):
    """Serializer for search suggestions"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    
    class Meta:
        model = SearchSuggestion
        fields = [
            'id', 'query', 'category', 'category_name',
            'category_slug', 'priority', 'is_active'
        ]
        read_only_fields = ['id']


class SearchFilterSerializer(serializers.ModelSerializer):
    """Serializer for search filters"""
    
    class Meta:
        model = SearchFilter
        fields = [
            'id', 'name', 'filters', 'usage_count',
            'is_preset', 'is_active'
        ]
        read_only_fields = ['id', 'usage_count']


class TaskSearchResultSerializer(TaskOwnerEmployerMixin, serializers.ModelSerializer):
    """Serializer for task search results (includes employer business branding)."""
    owner_name = serializers.SerializerMethodField()
    owner_username = serializers.SerializerMethodField()
    owner_image = serializers.SerializerMethodField()
    owner_logo_url = serializers.SerializerMethodField()
    owner_logo_text = serializers.SerializerMethodField()
    owner_logo_color = serializers.SerializerMethodField()
    owner_business_name = serializers.SerializerMethodField()
    owner_is_verified = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    budget = serializers.DecimalField(source='budget_amount', max_digits=10, decimal_places=2, read_only=True)
    location = serializers.SerializerMethodField()
    bid_count = serializers.IntegerField(source='bids_count', read_only=True)
    distance = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
        required=False,
        help_text='Distance in kilometers (if location-based search)'
    )

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

    def get_owner_is_verified(self, obj):
        owner = getattr(obj, 'owner', None)
        return bool(owner and getattr(owner, 'is_verified_tasker', False))

    def get_location(self, obj):
        parts = [obj.city, obj.state, obj.country]
        label = ', '.join(p for p in parts if p)
        return label or obj.address or ''

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'slug', 'description', 'status',
            'budget', 'budget_type', 'work_type', 'location',
            'latitude', 'longitude', 'due_date', 'urgency',
            'owner', 'owner_name', 'owner_username', 'owner_image',
            'owner_logo_url', 'owner_logo_text', 'owner_logo_color',
            'owner_business_name', 'owner_is_verified',
            'category', 'category_name', 'category_slug',
            'bid_count', 'distance', 'created_at'
        ]


class TaskerSearchResultSerializer(serializers.ModelSerializer):
    """Serializer for tasker search results"""
    skills = serializers.SerializerMethodField()
    badges = serializers.SerializerMethodField()
    completed_tasks = serializers.IntegerField(read_only=True)
    distance = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
        required=False,
        help_text='Distance in kilometers (if location-based search)'
    )
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name',
            'avatar', 'tagline', 'bio', 'location',
            'latitude', 'longitude', 'average_rating',
            'total_reviews', 'is_verified_tasker',
            'skills', 'badges', 'completed_tasks',
            'distance', 'created_at'
        ]
    
    def get_skills(self, obj):
        """Get user skills"""
        return [
            {
                'id': skill.id,
                'name': skill.skill_name,
                'level': skill.skill_level
            }
            for skill in obj.skills.all()[:5]
        ]
    
    def get_badges(self, obj):
        """Get user badges"""
        return [
            {
                'id': badge.id,
                'name': badge.badge_name,
                'icon': badge.badge_icon
            }
            for badge in obj.badges.all()[:5]
        ]


class CategorySearchResultSerializer(serializers.ModelSerializer):
    """Serializer for category search results"""
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    task_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'description', 'icon',
            'parent', 'parent_name', 'task_count', 'is_active'
        ]


class SearchRequestSerializer(serializers.Serializer):
    """Serializer for search request parameters"""
    query = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text='Search query text'
    )
    search_type = serializers.ChoiceField(
        choices=['tasks', 'taskers', 'categories', 'all'],
        default='tasks',
        help_text='Type of search to perform'
    )
    listing_kind = serializers.ChoiceField(
        choices=['task', 'job', 'project', 'service'],
        required=False,
        help_text='Filter task results by marketplace listing type (jobs, projects, services, or plain tasks)',
    )

    # Task filters
    category = serializers.IntegerField(
        required=False,
        help_text='Category ID'
    )
    min_budget = serializers.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=0,
        help_text='Minimum budget'
    )
    max_budget = serializers.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=0,
        help_text='Maximum budget'
    )
    budget_type = serializers.ChoiceField(
        choices=['fixed', 'hourly'],
        required=False,
        help_text='Budget type'
    )
    work_type = serializers.ChoiceField(
        choices=['remote', 'in_person', 'flexible'],
        required=False,
        help_text='Work type'
    )
    urgency = serializers.ChoiceField(
        choices=['low', 'medium', 'high', 'urgent'],
        required=False,
        help_text='Task urgency'
    )
    
    # Location filters
    latitude = serializers.DecimalField(
        required=False,
        max_digits=9,
        decimal_places=6,
        help_text='Latitude for location-based search'
    )
    longitude = serializers.DecimalField(
        required=False,
        max_digits=9,
        decimal_places=6,
        help_text='Longitude for location-based search'
    )
    radius = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        default=10,
        help_text='Search radius in kilometers'
    )
    
    # Tasker filters
    min_rating = serializers.DecimalField(
        required=False,
        max_digits=3,
        decimal_places=2,
        min_value=0,
        max_value=5,
        help_text='Minimum tasker rating'
    )
    verified_only = serializers.BooleanField(
        required=False,
        default=False,
        help_text='Show only verified taskers'
    )
    skills = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text='Required skills'
    )
    
    # Sorting
    sort_by = serializers.ChoiceField(
        choices=[
            'relevance', 'date', 'budget_asc', 'budget_desc',
            'rating', 'distance', 'popularity'
        ],
        default='relevance',
        help_text='Sort order'
    )
    
    # Pagination
    page = serializers.IntegerField(
        required=False,
        min_value=1,
        default=1,
        help_text='Page number'
    )
    page_size = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        default=20,
        help_text='Results per page'
    )


class SearchResponseSerializer(serializers.Serializer):
    """Serializer for search response"""
    query = serializers.CharField()
    search_type = serializers.CharField()
    total_results = serializers.IntegerField()
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    total_pages = serializers.IntegerField()
    results = serializers.ListField()
    filters_applied = serializers.DictField()
    suggestions = serializers.ListField(required=False)
    related_searches = serializers.ListField(required=False)


class AutocompleteRequestSerializer(serializers.Serializer):
    """Serializer for autocomplete request"""
    query = serializers.CharField(
        required=True,
        min_length=2,
        max_length=100,
        help_text='Partial search query'
    )
    search_type = serializers.ChoiceField(
        choices=['tasks', 'taskers', 'categories', 'all'],
        default='all',
        help_text='Type of suggestions to return'
    )
    limit = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=20,
        default=10,
        help_text='Maximum number of suggestions'
    )


class AutocompleteResponseSerializer(serializers.Serializer):
    """Serializer for autocomplete response"""
    suggestions = serializers.ListField()
    popular_searches = serializers.ListField()
    categories = serializers.ListField()


class TrendingSearchSerializer(serializers.Serializer):
    """Serializer for trending searches"""
    query = serializers.CharField()
    search_count = serializers.IntegerField()
    trend_direction = serializers.ChoiceField(
        choices=['up', 'down', 'stable']
    )
