from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Review,
    ReviewHelpful,
    ReviewReport,
    ReviewInvitation,
    ReviewPlatformSettings,
)


@admin.register(ReviewPlatformSettings)
class ReviewPlatformSettingsAdmin(admin.ModelAdmin):
    list_display = ['visibility_mode', 'edit_window_minutes', 'rate_limit_per_hour', 'updated_at']

    def has_add_permission(self, request):
        return not ReviewPlatformSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'task', 'reviewer', 'reviewee', 'overall_rating',
        'reviewer_type', 'is_public', 'is_finalized', 'is_flagged', 'created_at',
    ]
    list_filter = [
        'reviewer_type', 'overall_rating', 'is_public', 'is_finalized',
        'is_flagged', 'is_approved', 'created_at',
    ]
    search_fields = ['reviewer__email', 'reviewee__email', 'task__title', 'review_text']
    readonly_fields = ['id', 'created_at', 'updated_at', 'finalized_at', 'visible_at']
    raw_id_fields = ['task', 'reviewer', 'reviewee', 'moderated_by']

    fieldsets = (
        ('Parties', {'fields': ('id', 'task', 'reviewer', 'reviewee', 'reviewer_type', 'review_type')}),
        ('Content', {'fields': ('overall_rating', 'review_text', 'tags')}),
        ('Visibility', {'fields': ('is_public', 'visible_at', 'is_finalized', 'finalized_at')}),
        ('Moderation', {'fields': ('is_flagged', 'flag_reason', 'is_approved', 'moderated_by', 'moderated_at')}),
        ('Anti-abuse', {'fields': ('submitter_ip', 'submitter_user_agent')}),
        ('Response', {'fields': ('response_text', 'response_at')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(ReviewHelpful)
class ReviewHelpfulAdmin(admin.ModelAdmin):
    list_display = ['review', 'user', 'is_helpful', 'created_at']


@admin.register(ReviewReport)
class ReviewReportAdmin(admin.ModelAdmin):
    list_display = ['review', 'reporter', 'reason', 'is_resolved', 'created_at']
    list_filter = ['reason', 'is_resolved']


@admin.register(ReviewInvitation)
class ReviewInvitationAdmin(admin.ModelAdmin):
    list_display = ['task', 'invitee', 'reviewer_type', 'status', 'expires_at', 'completed_at']
    list_filter = ['status', 'reviewer_type']
