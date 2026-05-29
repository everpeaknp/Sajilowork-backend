"""
Admin interface for Analytics app.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Event, Metric, Funnel, FunnelStep, Cohort, Report


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    """Admin interface for Event model."""
    
    list_display = [
        'event_name', 'category_badge', 'event_type', 'user_email',
        'device_type', 'created_at'
    ]
    list_filter = ['category', 'event_type', 'device_type', 'created_at']
    search_fields = ['event_name', 'user__email', 'session_id']
    readonly_fields = ['id', 'created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Event Information', {
            'fields': ('id', 'user', 'session_id', 'category', 'event_type', 'event_name')
        }),
        ('Content Object', {
            'fields': ('content_type', 'object_id'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('properties', 'ip_address', 'user_agent', 'referrer')
        }),
        ('Location & Device', {
            'fields': ('country', 'city', 'device_type', 'os', 'browser')
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email if obj.user else 'Anonymous'
    user_email.short_description = 'User'
    
    def category_badge(self, obj):
        colors = {
            'user': '#3498db',
            'task': '#2ecc71',
            'bid': '#f39c12',
            'payment': '#e74c3c',
            'chat': '#9b59b6',
            'review': '#1abc9c',
            'search': '#34495e',
            'notification': '#95a5a6',
            'system': '#7f8c8d',
        }
        color = colors.get(obj.category, '#95a5a6')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_category_display()
        )
    category_badge.short_description = 'Category'


@admin.register(Metric)
class MetricAdmin(admin.ModelAdmin):
    """Admin interface for Metric model."""
    
    list_display = [
        'name', 'metric_type_badge', 'value', 'aggregation_period',
        'period_start', 'period_end'
    ]
    list_filter = ['metric_type', 'category', 'aggregation_period', 'period_start']
    search_fields = ['name', 'category']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'period_start'
    
    fieldsets = (
        ('Metric Information', {
            'fields': ('id', 'name', 'metric_type', 'category', 'value')
        }),
        ('Aggregation', {
            'fields': ('aggregation_period', 'period_start', 'period_end')
        }),
        ('Metadata', {
            'fields': ('dimensions', 'metadata')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def metric_type_badge(self, obj):
        colors = {
            'counter': '#3498db',
            'gauge': '#2ecc71',
            'histogram': '#f39c12',
            'rate': '#e74c3c',
        }
        color = colors.get(obj.metric_type, '#95a5a6')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_metric_type_display()
        )
    metric_type_badge.short_description = 'Type'


@admin.register(Funnel)
class FunnelAdmin(admin.ModelAdmin):
    """Admin interface for Funnel model."""
    
    list_display = ['name', 'step_count', 'is_active_badge', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Funnel Information', {
            'fields': ('id', 'name', 'description', 'steps')
        }),
        ('Configuration', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def step_count(self, obj):
        return len(obj.steps) if obj.steps else 0
    step_count.short_description = 'Steps'
    
    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background-color: #2ecc71; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-size: 11px;">Active</span>'
            )
        return format_html(
            '<span style="background-color: #95a5a6; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px;">Inactive</span>'
        )
    is_active_badge.short_description = 'Status'


@admin.register(FunnelStep)
class FunnelStepAdmin(admin.ModelAdmin):
    """Admin interface for FunnelStep model."""
    
    list_display = [
        'funnel', 'step_name', 'step_index', 'user_email',
        'completed_badge', 'created_at'
    ]
    list_filter = ['funnel', 'completed', 'created_at']
    search_fields = ['funnel__name', 'step_name', 'user__email', 'session_id']
    readonly_fields = ['id', 'created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Funnel Step Information', {
            'fields': ('id', 'funnel', 'user', 'session_id', 'step_name', 'step_index')
        }),
        ('Completion', {
            'fields': ('completed', 'completed_at')
        }),
        ('Metadata', {
            'fields': ('properties',)
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    
    def completed_badge(self, obj):
        if obj.completed:
            return format_html(
                '<span style="background-color: #2ecc71; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-size: 11px;">✓ Completed</span>'
            )
        return format_html(
            '<span style="background-color: #f39c12; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px;">Pending</span>'
        )
    completed_badge.short_description = 'Status'


@admin.register(Cohort)
class CohortAdmin(admin.ModelAdmin):
    """Admin interface for Cohort model."""
    
    list_display = [
        'name', 'member_count', 'is_active_badge', 'auto_update_badge',
        'last_updated', 'created_at'
    ]
    list_filter = ['is_active', 'auto_update', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'member_count', 'last_updated', 'created_at', 'updated_at']
    filter_horizontal = ['users']
    
    fieldsets = (
        ('Cohort Information', {
            'fields': ('id', 'name', 'description', 'criteria')
        }),
        ('Members', {
            'fields': ('users', 'member_count', 'last_updated')
        }),
        ('Configuration', {
            'fields': ('is_active', 'auto_update')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background-color: #2ecc71; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-size: 11px;">Active</span>'
            )
        return format_html(
            '<span style="background-color: #95a5a6; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px;">Inactive</span>'
        )
    is_active_badge.short_description = 'Status'
    
    def auto_update_badge(self, obj):
        if obj.auto_update:
            return format_html(
                '<span style="background-color: #3498db; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-size: 11px;">Auto</span>'
            )
        return format_html(
            '<span style="background-color: #95a5a6; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px;">Manual</span>'
        )
    auto_update_badge.short_description = 'Update'


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    """Admin interface for Report model."""
    
    list_display = [
        'name', 'report_type', 'frequency_badge', 'is_active_badge',
        'last_run', 'next_run'
    ]
    list_filter = ['report_type', 'frequency', 'is_active', 'last_run']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'last_run', 'next_run', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Report Information', {
            'fields': ('id', 'name', 'report_type', 'description')
        }),
        ('Configuration', {
            'fields': ('frequency', 'recipients', 'parameters')
        }),
        ('Status', {
            'fields': ('is_active', 'last_run', 'next_run')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def frequency_badge(self, obj):
        colors = {
            'daily': '#3498db',
            'weekly': '#2ecc71',
            'monthly': '#f39c12',
        }
        color = colors.get(obj.frequency, '#95a5a6')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_frequency_display()
        )
    frequency_badge.short_description = 'Frequency'
    
    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background-color: #2ecc71; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-size: 11px;">Active</span>'
            )
        return format_html(
            '<span style="background-color: #95a5a6; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px;">Inactive</span>'
        )
    is_active_badge.short_description = 'Status'
