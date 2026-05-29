"""
Admin configuration for User models.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db.models import Count
from django.shortcuts import render
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html
from datetime import timedelta

from apps.dashboard.admin_charts import (
    REPORT_PERIOD_CHOICES,
    daily_series,
    parse_report_period,
    rows_to_chart,
)
from apps.dashboard.services import DashboardService
from django.db.models.functions import TruncDate

from .models import User, UserSkill, UserBadge, UserDocument


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin interface for User model."""
    
    list_display = [
        'email', 'get_full_name', 'role', 'is_active', 'is_verified_tasker',
        'average_rating', 'tasks_completed', 'date_joined'
    ]
    list_filter = [
        'role', 'is_active', 'is_verified_tasker', 'email_verified',
        'phone_verified', 'identity_verified', 'date_joined'
    ]
    search_fields = ['email', 'first_name', 'last_name', 'username', 'phone']
    ordering = ['-date_joined']
    
    fieldsets = (
        ('Authentication', {
            'fields': ('email', 'username', 'password')
        }),
        ('Personal Info', {
            'fields': (
                'first_name', 'last_name', 'phone', 'date_of_birth', 'gender',
                'bio', 'tagline', 'profile_image', 'cover_image'
            )
        }),
        ('Role & Permissions', {
            'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Verification', {
            'fields': (
                'email_verified', 'phone_verified', 'identity_verified',
                'is_verified_tasker', 'account_suspended', 'suspended_until', 'suspension_reason'
            )
        }),
        ('Location', {
            'fields': ('address', 'city', 'state', 'country', 'postal_code', 'latitude', 'longitude')
        }),
        ('Statistics', {
            'fields': (
                'average_rating', 'total_reviews', 'tasks_completed', 'tasks_posted',
                'hourly_rate', 'response_time', 'completion_rate'
            )
        }),
        ('Financial', {
            'fields': ('wallet_balance', 'total_earned', 'total_spent')
        }),
        ('Preferences', {
            'fields': (
                'notification_enabled', 'email_notifications',
                'sms_notifications', 'push_notifications'
            )
        }),
        ('Metadata', {
            'fields': ('referral_code', 'referred_by', 'is_online', 'last_seen', 'date_joined', 'updated_at')
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 'username', 'password1', 'password2',
                'first_name', 'last_name', 'role'
            ),
        }),
    )
    
    readonly_fields = [
        'date_joined', 'updated_at', 'last_seen', 'average_rating',
        'total_reviews', 'tasks_completed', 'tasks_posted',
        'wallet_balance', 'total_earned', 'total_spent'
    ]
    
    def get_full_name(self, obj):
        """Display full name."""
        return obj.get_full_name()
    get_full_name.short_description = 'Full Name'

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                'stats/',
                self.admin_site.admin_view(self.user_stats_view),
                name='users_user_stats',
            ),
        ]
        return custom + urls

    def user_stats_view(self, request):
        """Platform user statistics (Jazzmin custom link)."""
        period_days, selected_days, period_label = parse_report_period(request)
        summary_days = period_days if period_days else 3650

        overview = DashboardService.get_platform_overview()
        growth = DashboardService.get_growth_metrics(days=summary_days)
        users_by_role = list(
            User.objects.values('role').annotate(count=Count('id')).order_by('-count')
        )
        signup_qs = User.objects.all()
        if period_days:
            since = timezone.now() - timedelta(days=period_days)
            signup_qs = signup_qs.filter(date_joined__gte=since)
        else:
            since = None

        recent_signups = signup_qs.order_by('-date_joined')[:20]

        trend_start = timezone.now() - timedelta(days=min(period_days or 30, 30))
        daily_signups = list(
            User.objects.filter(date_joined__gte=trend_start)
            .annotate(day=TruncDate('date_joined'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )
        charts = {
            'by_role': rows_to_chart(users_by_role, 'role', 'count', count_key='count'),
            'signups': daily_series(daily_signups),
            'growth': {
                'labels': ['New users', 'New tasks', 'New bids', 'Revenue (NPR)'],
                'values': [
                    growth['new_users'],
                    growth['new_tasks'],
                    growth['new_bids'],
                    float(growth['revenue']),
                ],
            },
        }
        kpis = [
            {'label': 'Total users', 'value': str(overview['users']['total']), 'hint': 'All registered'},
            {'label': 'Customers', 'value': str(overview['users']['customers']), 'hint': 'Posters'},
            {'label': 'Taskers', 'value': str(overview['users']['taskers']), 'hint': f"{overview['users']['verified_taskers']} verified"},
            {'label': 'New users', 'value': str(growth['new_users']), 'hint': period_label},
        ]
        context = {
            **self.admin_site.each_context(request),
            'title': 'User statistics',
            'period_label': period_label,
            'period_choices': REPORT_PERIOD_CHOICES,
            'selected_days': selected_days,
            'overview': overview,
            'growth': growth,
            'users_by_role': users_by_role,
            'recent_signups': recent_signups,
            'since': since,
            'charts': charts,
            'kpis': kpis,
        }
        return render(request, 'admin/users/user_stats.html', context)


@admin.register(UserSkill)
class UserSkillAdmin(admin.ModelAdmin):
    """Admin interface for UserSkill model."""

    list_display = [
        'user', 'name', 'category', 'proficiency_level',
        'years_of_experience', 'verified',
    ]
    list_filter = ['proficiency_level', 'verified', 'category']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'name']
    ordering = ['-verified', '-years_of_experience']
    actions = ['mark_verified', 'mark_unverified']

    fieldsets = (
        (None, {
            'fields': ('user', 'name', 'category')
        }),
        ('Proficiency', {
            'fields': ('proficiency_level', 'years_of_experience', 'verified')
        }),
    )

    @admin.action(description='Mark selected skills as verified')
    def mark_verified(self, request, queryset):
        updated = queryset.update(verified=True)
        self.message_user(request, f'{updated} skill(s) marked as verified.')

    @admin.action(description='Mark selected skills as not verified')
    def mark_unverified(self, request, queryset):
        updated = queryset.update(verified=False)
        self.message_user(request, f'{updated} skill(s) marked as not verified.')


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    """Admin interface for UserBadge model."""

    list_display = [
        'user',
        'badge_type',
        'name',
        'has_document',
        'is_verified',
        'verified_at',
        'earned_at',
    ]
    list_filter = ['badge_type', 'is_verified', 'earned_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'name']
    ordering = ['-earned_at']
    actions = ['mark_verified', 'mark_unverified']

    fieldsets = (
        (None, {
            'fields': (
                'user',
                'badge_type',
                'name',
                'description',
                'icon_url',
                'document_number',
                'verification_document',
                'is_verified',
                'verified_at',
            )
        }),
    )

    readonly_fields = ['earned_at']

    @admin.display(boolean=True, description='Document')
    def has_document(self, obj):
        return bool(obj.verification_document)

    @admin.action(description='Mark selected badges as verified (active)')
    def mark_verified(self, request, queryset):
        from django.utils import timezone

        updated = queryset.update(is_verified=True, verified_at=timezone.now())
        self.message_user(request, f'{updated} badge(s) marked as verified.')

    @admin.action(description='Mark selected badges as not verified')
    def mark_unverified(self, request, queryset):
        updated = queryset.update(is_verified=False, verified_at=None)
        self.message_user(request, f'{updated} badge(s) marked as not verified.')


@admin.register(UserDocument)
class UserDocumentAdmin(admin.ModelAdmin):
    """Admin interface for UserDocument model."""

    list_display = [
        'user', 'document_type', 'status', 'document_number',
        'uploaded_at', 'verified_at', 'verified_by',
    ]
    list_filter = ['document_type', 'status', 'uploaded_at']
    search_fields = [
        'user__email', 'user__first_name', 'user__last_name',
        'document_number',
    ]
    ordering = ['-uploaded_at']
    actions = ['approve_documents', 'reject_documents', 'mark_pending']

    fieldsets = (
        (None, {
            'fields': ('user', 'document_type', 'document_url', 'document_number'),
        }),
        ('Verification', {
            'fields': ('status', 'rejection_reason', 'verified_by', 'verified_at'),
        }),
    )

    readonly_fields = ['uploaded_at', 'verified_at']

    @admin.action(description='Approve selected documents')
    def approve_documents(self, request, queryset):
        from django.utils import timezone

        updated = queryset.update(
            status='approved',
            verified_by=request.user,
            verified_at=timezone.now(),
            rejection_reason='',
        )
        self.message_user(request, f'{updated} document(s) approved.')

    @admin.action(description='Reject selected documents')
    def reject_documents(self, request, queryset):
        updated = queryset.update(
            status='rejected',
            verified_by=None,
            verified_at=None,
        )
        self.message_user(request, f'{updated} document(s) marked as rejected.')

    @admin.action(description='Mark selected documents as pending')
    def mark_pending(self, request, queryset):
        updated = queryset.update(
            status='pending',
            verified_by=None,
            verified_at=None,
            rejection_reason='',
        )
        self.message_user(request, f'{updated} document(s) marked as pending.')

    def save_model(self, request, obj, form, change):
        """Auto-set verified_by when approving."""
        if change and obj.status == 'approved' and not obj.verified_by:
            obj.verified_by = request.user
            from django.utils import timezone

            obj.verified_at = timezone.now()
        super().save_model(request, obj, form, change)
