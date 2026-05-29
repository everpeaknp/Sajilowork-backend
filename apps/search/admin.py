"""
Search App Admin
"""
from django.contrib import admin
from django.utils.html import format_html
from apps.search.models import (
    SearchHistory, SavedSearch, PopularSearch,
    SearchSuggestion, SearchFilter
)


@admin.register(SearchHistory)
class SearchHistoryAdmin(admin.ModelAdmin):
    """Admin for search history"""
    list_display = [
        'id', 'user_display', 'query', 'search_type',
        'results_count', 'clicked_result', 'created_at'
    ]
    list_filter = ['search_type', 'clicked_result', 'created_at']
    search_fields = ['query', 'user__email', 'session_id']
    readonly_fields = [
        'user', 'query', 'search_type', 'filters',
        'results_count', 'clicked_result', 'clicked_result_id',
        'clicked_result_type', 'session_id', 'ip_address',
        'user_agent', 'created_at'
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def user_display(self, obj):
        """Display user or anonymous"""
        if obj.user:
            return obj.user.email
        return format_html('<span style="color: gray;">Anonymous</span>')
    user_display.short_description = 'User'
    
    def has_add_permission(self, request):
        """Disable add in admin"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable edit in admin"""
        return False


@admin.register(SavedSearch)
class SavedSearchAdmin(admin.ModelAdmin):
    """Admin for saved searches"""
    list_display = [
        'id', 'user', 'name', 'search_type',
        'notify_new_results', 'is_active_display', 'created_at'
    ]
    list_filter = ['search_type', 'notify_new_results', 'is_active', 'created_at']
    search_fields = ['name', 'query', 'user__email']
    readonly_fields = ['created_at', 'updated_at', 'last_notified_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'name', 'query', 'search_type')
        }),
        ('Filters', {
            'fields': ('filters',),
            'classes': ('collapse',)
        }),
        ('Notifications', {
            'fields': (
                'notify_new_results', 'notification_frequency',
                'last_notified_at', 'last_result_count'
            )
        }),
        ('Status', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
    )
    
    def is_active_display(self, obj):
        """Display active status with color"""
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Active</span>'
            )
        return format_html(
            '<span style="color: red;">✗ Inactive</span>'
        )
    is_active_display.short_description = 'Status'


@admin.register(PopularSearch)
class PopularSearchAdmin(admin.ModelAdmin):
    """Admin for popular searches"""
    list_display = [
        'id', 'query', 'search_count', 'click_through_rate',
        'is_trending_display', 'last_searched_at'
    ]
    list_filter = ['is_trending', 'last_searched_at']
    search_fields = ['query']
    readonly_fields = ['search_count', 'click_through_rate', 'last_searched_at', 'created_at']
    date_hierarchy = 'last_searched_at'
    ordering = ['-search_count', '-last_searched_at']
    
    def is_trending_display(self, obj):
        """Display trending status with icon"""
        if obj.is_trending:
            return format_html(
                '<span style="color: red; font-weight: bold;">🔥 Trending</span>'
            )
        return format_html(
            '<span style="color: gray;">-</span>'
        )
    is_trending_display.short_description = 'Trending'
    
    actions = ['mark_as_trending', 'unmark_as_trending']
    
    def mark_as_trending(self, request, queryset):
        """Mark searches as trending"""
        count = queryset.update(is_trending=True)
        self.message_user(request, f'{count} searches marked as trending')
    mark_as_trending.short_description = 'Mark as trending'
    
    def unmark_as_trending(self, request, queryset):
        """Unmark searches as trending"""
        count = queryset.update(is_trending=False)
        self.message_user(request, f'{count} searches unmarked as trending')
    unmark_as_trending.short_description = 'Unmark as trending'


@admin.register(SearchSuggestion)
class SearchSuggestionAdmin(admin.ModelAdmin):
    """Admin for search suggestions"""
    list_display = [
        'id', 'query', 'category', 'priority',
        'is_active_display', 'created_at'
    ]
    list_filter = ['is_active', 'category', 'created_at']
    search_fields = ['query', 'category__name']
    ordering = ['-priority', 'query']
    
    fieldsets = (
        ('Suggestion', {
            'fields': ('query', 'category', 'priority')
        }),
        ('Status', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def is_active_display(self, obj):
        """Display active status with color"""
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Active</span>'
            )
        return format_html(
            '<span style="color: red;">✗ Inactive</span>'
        )
    is_active_display.short_description = 'Status'


@admin.register(SearchFilter)
class SearchFilterAdmin(admin.ModelAdmin):
    """Admin for search filters"""
    list_display = [
        'id', 'name', 'usage_count', 'is_preset_display',
        'is_active_display', 'created_at'
    ]
    list_filter = ['is_preset', 'is_active', 'created_at']
    search_fields = ['name']
    readonly_fields = ['usage_count', 'created_at', 'updated_at']
    ordering = ['-usage_count', 'name']
    
    fieldsets = (
        ('Filter', {
            'fields': ('name', 'filters', 'is_preset')
        }),
        ('Statistics', {
            'fields': ('usage_count',)
        }),
        ('Status', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
    )
    
    def is_preset_display(self, obj):
        """Display preset status"""
        if obj.is_preset:
            return format_html(
                '<span style="color: blue; font-weight: bold;">✓ Preset</span>'
            )
        return format_html(
            '<span style="color: gray;">Custom</span>'
        )
    is_preset_display.short_description = 'Type'
    
    def is_active_display(self, obj):
        """Display active status with color"""
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Active</span>'
            )
        return format_html(
            '<span style="color: red;">✗ Inactive</span>'
        )
    is_active_display.short_description = 'Status'
