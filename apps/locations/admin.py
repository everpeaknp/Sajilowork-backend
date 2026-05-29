"""
Locations Admin Configuration
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Country, State, City, UserLocation, ServiceArea, LocationSearch


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    """Admin interface for Country model"""
    list_display = [
        'name', 'code', 'code3', 'phone_code',
        'currency_display', 'active_badge', 'created_at'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'code', 'code3']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'code', 'code3')
        }),
        ('Contact & Currency', {
            'fields': ('phone_code', 'currency_code', 'currency_symbol')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude')
        }),
        ('Status', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
    )
    
    def currency_display(self, obj):
        """Display currency with symbol"""
        return f"{obj.currency_code} ({obj.currency_symbol})"
    currency_display.short_description = 'Currency'
    
    def active_badge(self, obj):
        """Display active status as colored badge"""
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px;">Active</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; padding: 3px 10px; border-radius: 3px;">Inactive</span>'
        )
    active_badge.short_description = 'Status'


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    """Admin interface for State model"""
    list_display = [
        'name', 'code', 'country', 'active_badge', 'created_at'
    ]
    list_filter = ['is_active', 'country', 'created_at']
    search_fields = ['name', 'code', 'country__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['country__name', 'name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'country', 'name', 'code')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude')
        }),
        ('Status', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
    )
    
    def active_badge(self, obj):
        """Display active status as colored badge"""
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px;">Active</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; padding: 3px 10px; border-radius: 3px;">Inactive</span>'
        )
    active_badge.short_description = 'Status'


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    """Admin interface for City model"""
    list_display = [
        'name', 'state', 'population', 'popular_badge',
        'active_badge', 'created_at'
    ]
    list_filter = ['is_active', 'is_popular', 'state__country', 'created_at']
    search_fields = ['name', 'state__name', 'state__country__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-is_popular', 'name']
    actions = ['mark_as_popular', 'mark_as_not_popular']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'state', 'name')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude', 'timezone')
        }),
        ('Details', {
            'fields': ('population',)
        }),
        ('Status', {
            'fields': ('is_active', 'is_popular', 'created_at', 'updated_at')
        }),
    )
    
    def popular_badge(self, obj):
        """Display popular status as badge"""
        if obj.is_popular:
            return format_html(
                '<span style="background-color: #ff6b6b; color: white; padding: 3px 10px; border-radius: 3px;">🔥 Popular</span>'
            )
        return format_html(
            '<span style="background-color: #6c757d; color: white; padding: 3px 10px; border-radius: 3px;">Regular</span>'
        )
    popular_badge.short_description = 'Popularity'
    
    def active_badge(self, obj):
        """Display active status as colored badge"""
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px;">Active</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; padding: 3px 10px; border-radius: 3px;">Inactive</span>'
        )
    active_badge.short_description = 'Status'
    
    def mark_as_popular(self, request, queryset):
        """Mark selected cities as popular"""
        updated = queryset.update(is_popular=True)
        self.message_user(request, f'{updated} cities marked as popular.')
    mark_as_popular.short_description = 'Mark as popular'
    
    def mark_as_not_popular(self, request, queryset):
        """Mark selected cities as not popular"""
        updated = queryset.update(is_popular=False)
        self.message_user(request, f'{updated} cities marked as not popular.')
    mark_as_not_popular.short_description = 'Mark as not popular'


@admin.register(UserLocation)
class UserLocationAdmin(admin.ModelAdmin):
    """Admin interface for UserLocation model"""
    list_display = [
        'user', 'label', 'location_type', 'city',
        'default_badge', 'active_badge', 'created_at'
    ]
    list_filter = ['location_type', 'is_default', 'is_active', 'created_at']
    search_fields = ['user__email', 'label', 'address', 'city__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('User', {
            'fields': ('id', 'user')
        }),
        ('Location Details', {
            'fields': ('location_type', 'label', 'address', 'city')
        }),
        ('Coordinates', {
            'fields': ('latitude', 'longitude')
        }),
        ('Status', {
            'fields': ('is_default', 'is_active', 'created_at', 'updated_at')
        }),
    )
    
    def default_badge(self, obj):
        """Display default status as badge"""
        if obj.is_default:
            return format_html(
                '<span style="background-color: #007bff; color: white; padding: 3px 10px; border-radius: 3px;">⭐ Default</span>'
            )
        return format_html(
            '<span style="background-color: #6c757d; color: white; padding: 3px 10px; border-radius: 3px;">-</span>'
        )
    default_badge.short_description = 'Default'
    
    def active_badge(self, obj):
        """Display active status as colored badge"""
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px;">Active</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; padding: 3px 10px; border-radius: 3px;">Inactive</span>'
        )
    active_badge.short_description = 'Status'


@admin.register(ServiceArea)
class ServiceAreaAdmin(admin.ModelAdmin):
    """Admin interface for ServiceArea model"""
    list_display = [
        'user', 'city', 'radius_display', 'active_badge', 'created_at'
    ]
    list_filter = ['is_active', 'radius', 'created_at']
    search_fields = ['user__email', 'city__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'user', 'city')
        }),
        ('Service Details', {
            'fields': ('radius',)
        }),
        ('Status', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
    )
    
    def radius_display(self, obj):
        """Display radius with unit"""
        return f"{obj.radius} km"
    radius_display.short_description = 'Service Radius'
    
    def active_badge(self, obj):
        """Display active status as colored badge"""
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px;">Active</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; padding: 3px 10px; border-radius: 3px;">Inactive</span>'
        )
    active_badge.short_description = 'Status'


@admin.register(LocationSearch)
class LocationSearchAdmin(admin.ModelAdmin):
    """Admin interface for LocationSearch model"""
    list_display = [
        'query', 'user_display', 'results_count', 'radius_display', 'created_at'
    ]
    list_filter = ['created_at']
    search_fields = ['query', 'user__email', 'session_id', 'ip_address']
    readonly_fields = ['id', 'created_at']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Search Details', {
            'fields': ('id', 'user', 'session_id', 'query')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude', 'radius')
        }),
        ('Results', {
            'fields': ('results_count',)
        }),
        ('Tracking', {
            'fields': ('ip_address', 'user_agent', 'created_at')
        }),
    )
    
    def user_display(self, obj):
        """Display user or anonymous"""
        if obj.user:
            return format_html(
                '<span style="background-color: #007bff; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
                obj.user.email
            )
        return format_html(
            '<span style="background-color: #6c757d; color: white; padding: 3px 10px; border-radius: 3px;">Anonymous</span>'
        )
    user_display.short_description = 'User'
    
    def radius_display(self, obj):
        """Display radius with unit"""
        if obj.radius:
            return f"{obj.radius} km"
        return "-"
    radius_display.short_description = 'Radius'
    
    def has_add_permission(self, request):
        """Disable manual creation"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable editing"""
        return False
