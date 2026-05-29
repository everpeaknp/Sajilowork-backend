"""
Search App URLs
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.search.views import (
    SearchViewSet, SearchHistoryViewSet, SavedSearchViewSet,
    SearchSuggestionViewSet, SearchFilterViewSet
)

app_name = 'search'

router = DefaultRouter()
router.register(r'', SearchViewSet, basename='search')
router.register(r'history', SearchHistoryViewSet, basename='search-history')
router.register(r'saved', SavedSearchViewSet, basename='saved-search')
router.register(r'suggestions', SearchSuggestionViewSet, basename='search-suggestion')
router.register(r'filters', SearchFilterViewSet, basename='search-filter')

urlpatterns = [
    path('', include(router.urls)),
]
