"""
Admin interface for Bid management
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Avg, Sum
from .models import Bid, BidMessage, BidReview, BidNotification


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    """Admin interface for Bids"""
    
    list_display = [
        'id', 'task_link', 'tasker_link', 'amount_display', 
        'status_badge', 'created_at', 'is_counter_offer'
    ]
    list_filter = ['status', 'is_counter_offer', 'created_at', 'currency']
    search_fields = ['task__title', 'tasker__email', 'tasker__first_name', 'tasker__last_name', 'proposal']
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'accepted_at', 
        'rejected_at', 'withdrawn_at'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'task', 'tasker', 'status')
        }),
        ('Offer Details', {
            'fields': ('amount', 'currency', 'proposal', 'cover_letter', 
                      'estimated_duration', 'estimated_completion_date', 'attachments')
        }),
        ('Counter Offer', {
            'fields': ('is_counter_offer', 'original_bid'),
            'classes': ('collapse',)
        }),
        ('Status Details', {
            'fields': ('rejection_reason', 'withdrawal_reason')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'accepted_at', 
                      'rejected_at', 'withdrawn_at'),
            'classes': ('collapse',)
        }),
    )
    
    def task_link(self, obj):
        """Link to task"""
        url = reverse('admin:tasks_task_change', args=[obj.task.id])
        return format_html('<a href="{}">{}</a>', url, obj.task.title[:50])
    task_link.short_description = 'Task'
    
    def tasker_link(self, obj):
        """Link to tasker"""
        url = reverse('admin:users_user_change', args=[obj.tasker.id])
        return format_html('<a href="{}">{}</a>', url, obj.tasker.get_full_name())
    tasker_link.short_description = 'Tasker'
    
    def amount_display(self, obj):
        """Display amount with currency"""
        return f"{obj.currency} {obj.amount}"
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'pending': '#FFA500',
            'accepted': '#28A745',
            'rejected': '#DC3545',
            'withdrawn': '#6C757D',
            'expired': '#6C757D',
            'completed': '#007BFF'
        }
        color = colors.get(obj.status, '#6C757D')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('task', 'tasker', 'original_bid')


@admin.register(BidMessage)
class BidMessageAdmin(admin.ModelAdmin):
    """Admin interface for Bid Messages"""
    
    list_display = ['id', 'bid_link', 'sender_link', 'message_preview', 'created_at', 'is_read']
    list_filter = ['is_read', 'created_at']
    search_fields = ['bid__task__title', 'sender__email', 'message']
    readonly_fields = ['id', 'created_at', 'read_at']
    date_hierarchy = 'created_at'
    
    def bid_link(self, obj):
        """Link to bid"""
        url = reverse('admin:bids_bid_change', args=[obj.bid.id])
        return format_html('<a href="{}">Bid #{}</a>', url, str(obj.bid.id)[:8])
    bid_link.short_description = 'Bid'
    
    def sender_link(self, obj):
        """Link to sender"""
        url = reverse('admin:users_user_change', args=[obj.sender.id])
        return format_html('<a href="{}">{}</a>', url, obj.sender.get_full_name())
    sender_link.short_description = 'Sender'
    
    def message_preview(self, obj):
        """Show message preview"""
        return obj.message[:100] + '...' if len(obj.message) > 100 else obj.message
    message_preview.short_description = 'Message'


@admin.register(BidReview)
class BidReviewAdmin(admin.ModelAdmin):
    """Admin interface for Bid Reviews"""
    
    list_display = ['id', 'bid_link', 'reviewer_link', 'rating_stars', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['bid__task__title', 'reviewer__email', 'comment']
    readonly_fields = ['id', 'created_at']
    date_hierarchy = 'created_at'
    
    def bid_link(self, obj):
        """Link to bid"""
        url = reverse('admin:bids_bid_change', args=[obj.bid.id])
        return format_html('<a href="{}">Bid #{}</a>', url, str(obj.bid.id)[:8])
    bid_link.short_description = 'Bid'
    
    def reviewer_link(self, obj):
        """Link to reviewer"""
        url = reverse('admin:users_user_change', args=[obj.reviewer.id])
        return format_html('<a href="{}">{}</a>', url, obj.reviewer.get_full_name())
    reviewer_link.short_description = 'Reviewer'
    
    def rating_stars(self, obj):
        """Display rating as stars"""
        stars = '⭐' * obj.rating
        return format_html('<span style="font-size: 16px;">{}</span>', stars)
    rating_stars.short_description = 'Rating'


@admin.register(BidNotification)
class BidNotificationAdmin(admin.ModelAdmin):
    """Admin interface for Bid Notifications"""
    
    list_display = ['id', 'bid_link', 'recipient_link', 'notification_type', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['bid__task__title', 'recipient__email', 'message']
    readonly_fields = ['id', 'created_at', 'read_at']
    date_hierarchy = 'created_at'
    
    def bid_link(self, obj):
        """Link to bid"""
        url = reverse('admin:bids_bid_change', args=[obj.bid.id])
        return format_html('<a href="{}">Bid #{}</a>', url, str(obj.bid.id)[:8])
    bid_link.short_description = 'Bid'
    
    def recipient_link(self, obj):
        """Link to recipient"""
        url = reverse('admin:users_user_change', args=[obj.recipient.id])
        return format_html('<a href="{}">{}</a>', url, obj.recipient.get_full_name())
    recipient_link.short_description = 'Recipient'
