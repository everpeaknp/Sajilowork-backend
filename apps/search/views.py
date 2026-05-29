"""
Search App Views
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.core.paginator import Paginator
from django.db.models import Q

from apps.search.models import (
    SearchHistory, SavedSearch, PopularSearch,
    SearchSuggestion, SearchFilter
)
from apps.search.serializers import (
    SearchHistorySerializer, SavedSearchSerializer,
    SavedSearchCreateSerializer, PopularSearchSerializer,
    SearchSuggestionSerializer, SearchFilterSerializer,
    TaskSearchResultSerializer, TaskerSearchResultSerializer,
    CategorySearchResultSerializer, SearchRequestSerializer,
    SearchResponseSerializer, AutocompleteRequestSerializer,
    AutocompleteResponseSerializer, TrendingSearchSerializer
)
from apps.search.services import SearchService
from apps.search.permissions import IsOwnerOrReadOnly


class SearchViewSet(viewsets.ViewSet):
    """
    ViewSet for search operations
    """
    permission_classes = [AllowAny]
    
    def list(self, request):
        """
        Perform search across tasks, taskers, or categories
        
        Query Parameters:
            - query: Search query text
            - search_type: tasks, taskers, categories, or all
            - Various filters (see SearchRequestSerializer)
        """
        # Validate request
        serializer = SearchRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        query = data.get('query', '')
        search_type = data.get('search_type', 'tasks')
        page = data.get('page', 1)
        page_size = data.get('page_size', 20)
        
        # Extract filters
        filters = {
            'category': data.get('category'),
            'min_budget': data.get('min_budget'),
            'max_budget': data.get('max_budget'),
            'budget_type': data.get('budget_type'),
            'work_type': data.get('work_type'),
            'urgency': data.get('urgency'),
            'latitude': data.get('latitude'),
            'longitude': data.get('longitude'),
            'radius': data.get('radius', 10),
            'min_rating': data.get('min_rating'),
            'verified_only': data.get('verified_only', False),
            'skills': data.get('skills', []),
            'sort_by': data.get('sort_by', 'relevance'),
        }
        
        # Remove None values
        filters = {k: v for k, v in filters.items() if v is not None}
        
        # Perform search
        results = []
        total_results = 0
        
        if search_type == 'tasks':
            queryset = SearchService.search_tasks(query, filters, request.user if request.user.is_authenticated else None)
            total_results = queryset.count()
            
            # Paginate
            paginator = Paginator(queryset, page_size)
            page_obj = paginator.get_page(page)
            
            results = TaskSearchResultSerializer(page_obj, many=True).data
            
        elif search_type == 'taskers':
            queryset = SearchService.search_taskers(query, filters, request.user if request.user.is_authenticated else None)
            total_results = queryset.count()
            
            # Paginate
            paginator = Paginator(queryset, page_size)
            page_obj = paginator.get_page(page)
            
            results = TaskerSearchResultSerializer(page_obj, many=True).data
            
        elif search_type == 'categories':
            queryset = SearchService.search_categories(query, filters, request.user if request.user.is_authenticated else None)
            total_results = queryset.count()
            
            # Paginate
            paginator = Paginator(queryset, page_size)
            page_obj = paginator.get_page(page)
            
            results = CategorySearchResultSerializer(page_obj, many=True).data
            
        elif search_type == 'all':
            # Search all types
            tasks = SearchService.search_tasks(query, filters, request.user if request.user.is_authenticated else None)[:5]
            taskers = SearchService.search_taskers(query, filters, request.user if request.user.is_authenticated else None)[:5]
            categories = SearchService.search_categories(query, filters, request.user if request.user.is_authenticated else None)[:5]
            
            results = {
                'tasks': TaskSearchResultSerializer(tasks, many=True).data,
                'taskers': TaskerSearchResultSerializer(taskers, many=True).data,
                'categories': CategorySearchResultSerializer(categories, many=True).data,
            }
            total_results = len(results['tasks']) + len(results['taskers']) + len(results['categories'])
        
        # Record search
        SearchService.record_search(
            user=request.user if request.user.is_authenticated else None,
            query=query,
            search_type=search_type,
            filters=filters,
            results_count=total_results,
            request=request
        )
        
        # Get suggestions and related searches
        suggestions = []
        related_searches = []
        
        if query and len(query) >= 3:
            autocomplete = SearchService.get_autocomplete_suggestions(query, search_type, limit=5)
            suggestions = autocomplete.get('suggestions', [])
            related_searches = SearchService.get_related_searches(query, limit=5)
        
        # Build response
        response_data = {
            'query': query,
            'search_type': search_type,
            'total_results': total_results,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_results + page_size - 1) // page_size if search_type != 'all' else 1,
            'results': results,
            'filters_applied': filters,
            'suggestions': suggestions,
            'related_searches': related_searches,
        }
        
        return Response(response_data)
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def autocomplete(self, request):
        """
        Get autocomplete suggestions
        
        Query Parameters:
            - query: Partial search query (min 2 characters)
            - search_type: Type of suggestions (default: all)
            - limit: Maximum suggestions (default: 10)
        """
        serializer = AutocompleteRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        suggestions = SearchService.get_autocomplete_suggestions(
            query=data['query'],
            search_type=data.get('search_type', 'all'),
            limit=data.get('limit', 10)
        )
        
        response_serializer = AutocompleteResponseSerializer(suggestions)
        return Response(response_serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def trending(self, request):
        """Get trending searches"""
        limit = int(request.query_params.get('limit', 10))
        trending = SearchService.get_trending_searches(limit=limit)
        serializer = PopularSearchSerializer(trending, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def popular(self, request):
        """Get popular searches"""
        limit = int(request.query_params.get('limit', 20))
        popular = PopularSearch.objects.all().order_by('-search_count')[:limit]
        serializer = PopularSearchSerializer(popular, many=True)
        return Response(serializer.data)


class SearchHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for search history (read-only)
    """
    serializer_class = SearchHistorySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Get search history for current user"""
        return SearchHistory.objects.filter(
            user=self.request.user
        ).order_by('-created_at')
    
    @action(detail=False, methods=['delete'])
    def clear(self, request):
        """Clear all search history for current user"""
        count = SearchHistory.objects.filter(user=request.user).delete()[0]
        return Response({
            'message': f'Cleared {count} search history items',
            'count': count
        })


class SavedSearchViewSet(viewsets.ModelViewSet):
    """
    ViewSet for saved searches
    """
    serializer_class = SavedSearchSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    
    def get_queryset(self):
        """Get saved searches for current user"""
        return SavedSearch.objects.filter(
            user=self.request.user
        ).order_by('-created_at')
    
    def get_serializer_class(self):
        """Use different serializer for create"""
        if self.action == 'create':
            return SavedSearchCreateSerializer
        return SavedSearchSerializer
    
    def perform_create(self, serializer):
        """Set user when creating saved search"""
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle active status of saved search"""
        saved_search = self.get_object()
        saved_search.is_active = not saved_search.is_active
        saved_search.save(update_fields=['is_active'])
        
        serializer = self.get_serializer(saved_search)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def check_updates(self, request, pk=None):
        """Check for new results in saved search"""
        saved_search = self.get_object()
        new_count = SearchService.check_saved_search_updates(saved_search)
        
        return Response({
            'saved_search_id': saved_search.id,
            'new_results': new_count,
            'total_results': saved_search.last_result_count,
            'message': f'Found {new_count} new results' if new_count > 0 else 'No new results'
        })
    
    @action(detail=True, methods=['get'])
    def execute(self, request, pk=None):
        """Execute saved search and return results"""
        saved_search = self.get_object()
        
        # Build search request
        filters = saved_search.filters.copy()
        filters['sort_by'] = filters.get('sort_by', 'relevance')
        
        # Perform search
        if saved_search.search_type == 'tasks':
            queryset = SearchService.search_tasks(
                saved_search.query,
                filters,
                request.user
            )
            results = TaskSearchResultSerializer(queryset[:20], many=True).data
        elif saved_search.search_type == 'taskers':
            queryset = SearchService.search_taskers(
                saved_search.query,
                filters,
                request.user
            )
            results = TaskerSearchResultSerializer(queryset[:20], many=True).data
        else:
            queryset = SearchService.search_categories(
                saved_search.query,
                filters,
                request.user
            )
            results = CategorySearchResultSerializer(queryset[:20], many=True).data
        
        return Response({
            'saved_search': SavedSearchSerializer(saved_search).data,
            'results': results,
            'total_results': queryset.count()
        })


class SearchSuggestionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for search suggestions (read-only for users, admin can manage)
    """
    serializer_class = SearchSuggestionSerializer
    permission_classes = [AllowAny]
    queryset = SearchSuggestion.objects.filter(is_active=True).order_by('-priority', 'query')


class SearchFilterViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for search filter presets (read-only)
    """
    serializer_class = SearchFilterSerializer
    permission_classes = [AllowAny]
    queryset = SearchFilter.objects.filter(
        is_preset=True,
        is_active=True
    ).order_by('-usage_count', 'name')
