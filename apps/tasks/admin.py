"""
Admin configuration for Task models.
"""
from django.contrib import admin
from django.db.models import Count, Sum
from django.shortcuts import render
from django.urls import path
from django.utils.html import format_html

from datetime import timedelta

from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.dashboard.admin_charts import (
    REPORT_PERIOD_CHOICES,
    daily_series,
    parse_report_period,
    rows_to_chart,
)
from apps.dashboard.services import DashboardService

from .models import (
    Task, Category, TaskAttachment, TaskBookmark,
    TaskView, TaskQuestion, TaskReport
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin interface for Category model."""
    
    list_display = ['name', 'slug', 'parent', 'is_active', 'order', 'task_count']
    list_filter = ['is_active', 'parent']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['order', 'name']
    
    def task_count(self, obj):
        """Display number of tasks in category."""
        return obj.tasks.count()
    task_count.short_description = 'Tasks'


class TaskAttachmentInline(admin.TabularInline):
    """Inline admin for task attachments."""
    model = TaskAttachment
    extra = 0
    readonly_fields = ['uploaded_by', 'uploaded_at']


class TaskQuestionInline(admin.TabularInline):
    """Inline admin for task questions."""
    model = TaskQuestion
    extra = 0
    readonly_fields = ['asked_by', 'created_at']


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """Admin interface for Task model."""
    
    list_display = [
        'title', 'owner', 'status', 'budget_amount', 'category',
        'city', 'bids_count', 'views_count', 'created_at'
    ]
    list_filter = [
        'status', 'work_type', 'location_type', 'urgency',
        'is_public', 'is_featured', 'created_at'
    ]
    search_fields = ['title', 'description', 'owner__email', 'city']
    readonly_fields = [
        'slug', 'views_count', 'bids_count', 'bookmarks_count',
        'created_at', 'updated_at', 'published_at'
    ]
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    inlines = [TaskAttachmentInline, TaskQuestionInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'description', 'category', 'owner')
        }),
        ('Task Details', {
            'fields': (
                'status', 'work_type', 'urgency', 'budget_type',
                'budget_amount', 'budget_currency'
            )
        }),
        ('Location', {
            'fields': (
                'location_type', 'address', 'city', 'state',
                'country', 'postal_code', 'latitude', 'longitude'
            )
        }),
        ('Dates', {
            'fields': ('due_date', 'start_date', 'completion_date')
        }),
        ('Assignment', {
            'fields': ('assigned_tasker',)
        }),
        ('Settings', {
            'fields': (
                'is_public', 'is_featured', 'allow_bids', 'auto_accept_bid'
            )
        }),
        ('Statistics', {
            'fields': ('views_count', 'bids_count', 'bookmarks_count')
        }),
        ('Metadata', {
            'fields': ('tags', 'requirements', 'created_at', 'updated_at', 'published_at')
        }),
    )
    
    actions = ['publish_tasks', 'feature_tasks', 'unfeature_tasks']
    
    def publish_tasks(self, request, queryset):
        """Publish selected draft tasks."""
        count = 0
        for task in queryset.filter(status='draft'):
            task.publish()
            count += 1
        self.message_user(request, f'{count} tasks published successfully.')
    publish_tasks.short_description = 'Publish selected draft tasks'
    
    def feature_tasks(self, request, queryset):
        """Feature selected tasks."""
        count = queryset.update(is_featured=True)
        self.message_user(request, f'{count} tasks featured successfully.')
    feature_tasks.short_description = 'Feature selected tasks'
    
    def unfeature_tasks(self, request, queryset):
        """Unfeature selected tasks."""
        count = queryset.update(is_featured=False)
        self.message_user(request, f'{count} tasks unfeatured successfully.')
    unfeature_tasks.short_description = 'Unfeature selected tasks'

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                'analytics/',
                self.admin_site.admin_view(self.task_analytics_view),
                name='tasks_task_analytics',
            ),
        ]
        return custom + urls

    def task_analytics_view(self, request):
        """Platform task analytics (Jazzmin custom link)."""
        period_days, selected_days, period_label = parse_report_period(request)
        summary_days = period_days if period_days else 3650

        overview = DashboardService.get_platform_overview()
        growth = DashboardService.get_growth_metrics(days=summary_days)
        task_qs = Task.objects.all()
        if period_days:
            start = timezone.now() - timedelta(days=period_days)
            task_qs = task_qs.filter(created_at__gte=start)

        by_status = list(task_qs.values('status').annotate(count=Count('id')).order_by('-count'))
        budget_totals = task_qs.aggregate(total_budget=Sum('budget_amount'))
        by_category = DashboardService.get_category_statistics()
        recent_tasks = task_qs.select_related('owner', 'category').order_by('-created_at')[:20]

        trend_start = timezone.now() - timedelta(days=min(period_days or 30, 30))
        daily_tasks = list(
            Task.objects.filter(created_at__gte=trend_start)
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )
        category_chart_rows = [
            {'name': c['name'], 'total': c['total_tasks']} for c in by_category[:8]
        ]
        charts = {
            'by_status': rows_to_chart(by_status, 'status', 'count', count_key='count'),
            'daily': daily_series(daily_tasks),
            'categories': rows_to_chart(
                [{'label': r['name'], 'total': r['total']} for r in category_chart_rows],
                'label',
                'total',
            ),
            'growth': {
                'labels': ['New tasks', 'New bids'],
                'values': [growth['new_tasks'], growth['new_bids']],
            },
        }
        kpis = [
            {'label': 'Total tasks', 'value': str(overview['tasks']['total']), 'hint': 'All time'},
            {'label': 'Open tasks', 'value': str(overview['tasks']['open']), 'hint': 'Currently open'},
            {'label': 'Completed', 'value': str(overview['tasks']['completed']), 'hint': f"{overview['tasks']['completion_rate']:.1f}% completion"},
            {'label': 'Total budget', 'value': f"NPR {float(budget_totals['total_budget'] or 0):,.2f}", 'hint': period_label},
        ]
        context = {
            **self.admin_site.each_context(request),
            'title': 'Task analytics',
            'period_label': period_label,
            'period_choices': REPORT_PERIOD_CHOICES,
            'selected_days': selected_days,
            'overview': overview,
            'growth': growth,
            'by_status': by_status,
            'budget_totals': budget_totals,
            'by_category': by_category,
            'recent_tasks': recent_tasks,
            'charts': charts,
            'kpis': kpis,
        }
        return render(request, 'admin/tasks/task_analytics.html', context)


@admin.register(TaskAttachment)
class TaskAttachmentAdmin(admin.ModelAdmin):
    """Admin interface for TaskAttachment model."""
    
    list_display = ['task', 'file_name', 'file_type', 'file_size', 'uploaded_by', 'uploaded_at']
    list_filter = ['file_type', 'uploaded_at']
    search_fields = ['task__title', 'file_name', 'uploaded_by__email']
    readonly_fields = ['uploaded_at']
    ordering = ['-uploaded_at']


@admin.register(TaskBookmark)
class TaskBookmarkAdmin(admin.ModelAdmin):
    """Admin interface for TaskBookmark model."""
    
    list_display = ['user', 'task', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__email', 'task__title']
    ordering = ['-created_at']


@admin.register(TaskView)
class TaskViewAdmin(admin.ModelAdmin):
    """Admin interface for TaskView model."""
    
    list_display = ['task', 'user', 'ip_address', 'viewed_at']
    list_filter = ['viewed_at']
    search_fields = ['task__title', 'user__email', 'ip_address']
    readonly_fields = ['viewed_at']
    ordering = ['-viewed_at']


@admin.register(TaskQuestion)
class TaskQuestionAdmin(admin.ModelAdmin):
    """Admin interface for TaskQuestion model."""
    
    list_display = ['task', 'asked_by', 'is_answered', 'is_public', 'created_at']
    list_filter = ['is_public', 'created_at']
    search_fields = ['task__title', 'asked_by__email', 'question']
    readonly_fields = ['created_at', 'answered_at']
    ordering = ['-created_at']
    
    fieldsets = (
        (None, {
            'fields': ('task', 'asked_by', 'question', 'answer')
        }),
        ('Settings', {
            'fields': ('is_public', 'created_at', 'answered_at')
        }),
    )


@admin.register(TaskReport)
class TaskReportAdmin(admin.ModelAdmin):
    """Admin interface for TaskReport model."""
    
    list_display = ['task', 'reported_by', 'reason', 'status', 'created_at']
    list_filter = ['reason', 'status', 'created_at']
    search_fields = ['task__title', 'reported_by__email', 'description']
    readonly_fields = ['created_at', 'reviewed_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Report Details', {
            'fields': ('task', 'reported_by', 'reason', 'description')
        }),
        ('Review', {
            'fields': ('status', 'admin_notes', 'reviewed_by', 'reviewed_at')
        }),
    )
    
    actions = ['mark_reviewed', 'mark_resolved', 'mark_dismissed']
    
    def mark_reviewed(self, request, queryset):
        """Mark reports as reviewed."""
        from django.utils import timezone
        count = queryset.update(status='reviewed', reviewed_by=request.user, reviewed_at=timezone.now())
        self.message_user(request, f'{count} reports marked as reviewed.')
    mark_reviewed.short_description = 'Mark as reviewed'
    
    def mark_resolved(self, request, queryset):
        """Mark reports as resolved."""
        from django.utils import timezone
        count = queryset.update(status='resolved', reviewed_by=request.user, reviewed_at=timezone.now())
        self.message_user(request, f'{count} reports marked as resolved.')
    mark_resolved.short_description = 'Mark as resolved'
    
    def mark_dismissed(self, request, queryset):
        """Mark reports as dismissed."""
        from django.utils import timezone
        count = queryset.update(status='dismissed', reviewed_by=request.user, reviewed_at=timezone.now())
        self.message_user(request, f'{count} reports marked as dismissed.')
    mark_dismissed.short_description = 'Mark as dismissed'
