"""
Search App Services - Business logic for search functionality
"""
from django.db.models import Q, Count, Avg, F, ExpressionWrapper, FloatField
from django.db.models.functions import ACos, Cos, Radians, Sin
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import math

from apps.search.models import (
    SearchHistory, SavedSearch, PopularSearch,
    SearchSuggestion, SearchFilter
)
from apps.tasks.models import Task, Category
from apps.users.models import User


class SearchService:
    """Service for handling search operations"""
    
    @staticmethod
    def search_tasks(query, filters, user=None):
        """
        Search for tasks with filters
        
        Args:
            query: Search query string
            filters: Dictionary of filters
            user: Current user (optional)
        
        Returns:
            QuerySet of tasks
        """
        tasks = Task.objects.filter(status='open').select_related(
            'owner', 'category'
        ).annotate(
            bid_count=Count('bids')
        )
        
        # Text search
        if query:
            tasks = tasks.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(tags__icontains=query) |
                Q(category__name__icontains=query)
            )
        
        # Category filter
        if filters.get('category'):
            tasks = tasks.filter(category_id=filters['category'])
        
        # Budget filters
        if filters.get('min_budget'):
            tasks = tasks.filter(budget__gte=filters['min_budget'])
        if filters.get('max_budget'):
            tasks = tasks.filter(budget__lte=filters['max_budget'])
        
        # Budget type filter
        if filters.get('budget_type'):
            tasks = tasks.filter(budget_type=filters['budget_type'])
        
        # Work type filter
        if filters.get('work_type'):
            tasks = tasks.filter(work_type=filters['work_type'])
        
        # Urgency filter
        if filters.get('urgency'):
            tasks = tasks.filter(urgency=filters['urgency'])
        
        # Location-based search
        if filters.get('latitude') and filters.get('longitude'):
            tasks = SearchService._apply_location_filter(
                tasks,
                filters['latitude'],
                filters['longitude'],
                filters.get('radius', 10)
            )
        
        # Sorting
        sort_by = filters.get('sort_by', 'relevance')
        tasks = SearchService._apply_sorting(tasks, sort_by, query)
        
        return tasks.distinct()
    
    @staticmethod
    def search_taskers(query, filters, user=None):
        """
        Search for taskers with filters
        
        Args:
            query: Search query string
            filters: Dictionary of filters
            user: Current user (optional)
        
        Returns:
            QuerySet of users
        """
        taskers = User.objects.filter(
            role='tasker',
            is_active=True
        ).select_related().prefetch_related(
            'skills', 'badges'
        ).annotate(
            completed_tasks=Count(
                'assigned_tasks',
                filter=Q(assigned_tasks__status='completed')
            )
        )
        
        # Text search
        if query:
            taskers = taskers.filter(
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(tagline__icontains=query) |
                Q(bio__icontains=query) |
                Q(skills__skill_name__icontains=query)
            )
        
        # Verified filter
        if filters.get('verified_only'):
            taskers = taskers.filter(is_verified_tasker=True)
        
        # Rating filter
        if filters.get('min_rating'):
            taskers = taskers.filter(average_rating__gte=filters['min_rating'])
        
        # Skills filter
        if filters.get('skills'):
            for skill in filters['skills']:
                taskers = taskers.filter(skills__skill_name__icontains=skill)
        
        # Location-based search
        if filters.get('latitude') and filters.get('longitude'):
            taskers = SearchService._apply_location_filter(
                taskers,
                filters['latitude'],
                filters['longitude'],
                filters.get('radius', 10)
            )
        
        # Sorting
        sort_by = filters.get('sort_by', 'rating')
        if sort_by == 'rating':
            taskers = taskers.order_by('-average_rating', '-total_reviews')
        elif sort_by == 'date':
            taskers = taskers.order_by('-created_at')
        elif sort_by == 'distance' and filters.get('latitude'):
            pass  # Already sorted by distance in location filter
        else:
            taskers = taskers.order_by('-completed_tasks', '-average_rating')
        
        return taskers.distinct()
    
    @staticmethod
    def search_categories(query, filters, user=None):
        """
        Search for categories
        
        Args:
            query: Search query string
            filters: Dictionary of filters
            user: Current user (optional)
        
        Returns:
            QuerySet of categories
        """
        categories = Category.objects.filter(
            is_active=True
        ).annotate(
            task_count=Count('tasks', filter=Q(tasks__status='open'))
        )
        
        # Text search
        if query:
            categories = categories.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query)
            )
        
        # Sort by task count and relevance
        categories = categories.order_by('-task_count', 'name')
        
        return categories
    
    @staticmethod
    def _apply_location_filter(queryset, latitude, longitude, radius_km):
        """
        Apply location-based filtering using Haversine formula
        
        Args:
            queryset: Base queryset
            latitude: Search latitude
            longitude: Search longitude
            radius_km: Search radius in kilometers
        
        Returns:
            Filtered queryset with distance annotation
        """
        # Haversine formula for distance calculation
        # Distance in kilometers
        lat_rad = math.radians(float(latitude))
        lon_rad = math.radians(float(longitude))
        
        # Filter by approximate bounding box first (faster)
        lat_range = radius_km / 111.0  # 1 degree latitude ≈ 111 km
        lon_range = radius_km / (111.0 * math.cos(lat_rad))
        
        queryset = queryset.filter(
            latitude__range=(float(latitude) - lat_range, float(latitude) + lat_range),
            longitude__range=(float(longitude) - lon_range, float(longitude) + lon_range)
        )
        
        # Calculate exact distance using Haversine
        queryset = queryset.annotate(
            distance=ExpressionWrapper(
                6371 * ACos(
                    Cos(Radians(latitude)) *
                    Cos(Radians(F('latitude'))) *
                    Cos(Radians(F('longitude')) - Radians(longitude)) +
                    Sin(Radians(latitude)) *
                    Sin(Radians(F('latitude')))
                ),
                output_field=FloatField()
            )
        ).filter(distance__lte=radius_km).order_by('distance')
        
        return queryset
    
    @staticmethod
    def _apply_sorting(queryset, sort_by, query=None):
        """Apply sorting to queryset"""
        if sort_by == 'date':
            return queryset.order_by('-created_at')
        elif sort_by == 'budget_asc':
            return queryset.order_by('budget')
        elif sort_by == 'budget_desc':
            return queryset.order_by('-budget')
        elif sort_by == 'popularity':
            return queryset.order_by('-bid_count', '-created_at')
        elif sort_by == 'distance':
            return queryset.order_by('distance')
        else:  # relevance (default)
            if query:
                # Simple relevance: title match > description match
                return queryset.order_by('-created_at')
            return queryset.order_by('-created_at')
    
    @staticmethod
    def record_search(user, query, search_type, filters, results_count, request=None):
        """
        Record search in history
        
        Args:
            user: User who performed search (can be None)
            query: Search query
            search_type: Type of search
            filters: Applied filters
            results_count: Number of results
            request: HTTP request object (optional)
        
        Returns:
            SearchHistory instance
        """
        session_id = None
        ip_address = None
        user_agent = ''
        
        if request:
            session_id = request.session.session_key
            ip_address = SearchService._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        history = SearchHistory.objects.create(
            user=user,
            query=query,
            search_type=search_type,
            filters=filters,
            results_count=results_count,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Update popular searches
        SearchService._update_popular_search(query)
        
        return history
    
    @staticmethod
    def _get_client_ip(request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    @staticmethod
    def _update_popular_search(query):
        """Update popular search statistics"""
        if not query or len(query) < 3:
            return
        
        popular, created = PopularSearch.objects.get_or_create(
            query=query.lower(),
            defaults={'search_count': 1}
        )
        
        if not created:
            popular.search_count = F('search_count') + 1
            popular.save(update_fields=['search_count', 'last_searched_at'])
    
    @staticmethod
    def get_autocomplete_suggestions(query, search_type='all', limit=10):
        """
        Get autocomplete suggestions
        
        Args:
            query: Partial search query
            search_type: Type of suggestions
            limit: Maximum number of suggestions
        
        Returns:
            Dictionary with suggestions
        """
        suggestions = []
        popular_searches = []
        categories = []
        
        # Get curated suggestions
        if search_type in ['all', 'tasks']:
            suggestions = list(
                SearchSuggestion.objects.filter(
                    query__istartswith=query,
                    is_active=True
                ).values_list('query', flat=True)[:limit]
            )
        
        # Get popular searches
        popular_searches = list(
            PopularSearch.objects.filter(
                query__icontains=query
            ).order_by('-search_count')[:limit].values_list('query', flat=True)
        )
        
        # Get matching categories
        if search_type in ['all', 'categories']:
            categories = list(
                Category.objects.filter(
                    name__icontains=query,
                    is_active=True
                ).values('id', 'name', 'slug')[:limit]
            )
        
        return {
            'suggestions': suggestions,
            'popular_searches': popular_searches,
            'categories': categories
        }
    
    @staticmethod
    def get_trending_searches(limit=10):
        """Get trending searches"""
        # Searches from last 7 days
        week_ago = timezone.now() - timedelta(days=7)
        
        trending = PopularSearch.objects.filter(
            last_searched_at__gte=week_ago,
            is_trending=True
        ).order_by('-search_count')[:limit]
        
        return trending
    
    @staticmethod
    def get_related_searches(query, limit=5):
        """Get related search suggestions"""
        # Find searches with similar terms
        words = query.lower().split()
        related = []
        
        for word in words:
            if len(word) >= 3:
                searches = PopularSearch.objects.filter(
                    query__icontains=word
                ).exclude(
                    query=query.lower()
                ).order_by('-search_count')[:limit]
                
                related.extend([s.query for s in searches])
        
        # Remove duplicates and limit
        return list(dict.fromkeys(related))[:limit]
    
    @staticmethod
    def check_saved_search_updates(saved_search):
        """
        Check for new results in saved search
        
        Args:
            saved_search: SavedSearch instance
        
        Returns:
            Number of new results
        """
        filters = saved_search.filters
        
        if saved_search.search_type == 'tasks':
            results = SearchService.search_tasks(
                saved_search.query,
                filters
            )
        elif saved_search.search_type == 'taskers':
            results = SearchService.search_taskers(
                saved_search.query,
                filters
            )
        else:
            results = SearchService.search_categories(
                saved_search.query,
                filters
            )
        
        new_count = results.count()
        old_count = saved_search.last_result_count
        
        # Update saved search
        saved_search.last_result_count = new_count
        saved_search.save(update_fields=['last_result_count'])
        
        return max(0, new_count - old_count)
