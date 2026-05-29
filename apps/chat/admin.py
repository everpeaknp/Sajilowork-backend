"""
Admin interface for chat app.
"""
from django.contrib import admin
from .models import (
    Conversation, Message, TypingIndicator,
    MessageReaction, ConversationMute, MessageReport
)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """Admin interface for Conversation model."""
    list_display = ['id', 'task', 'bid', 'created_at', 'last_message_at', 'is_active', 'is_archived']
    list_filter = ['is_active', 'is_archived', 'created_at']
    search_fields = ['id', 'task__title', 'bid__id']
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_message_at']
    filter_horizontal = ['participants']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'task', 'bid', 'participants')
        }),
        ('Status', {
            'fields': ('is_active', 'is_archived')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_message_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Admin interface for Message model."""
    list_display = ['id', 'conversation', 'sender', 'message_type', 'content_preview', 'is_read', 'is_deleted', 'created_at']
    list_filter = ['message_type', 'is_read', 'is_edited', 'is_deleted', 'created_at']
    search_fields = ['id', 'content', 'sender__email', 'sender__first_name', 'sender__last_name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'read_at']
    raw_id_fields = ['conversation', 'sender', 'reply_to']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'conversation', 'sender', 'message_type')
        }),
        ('Content', {
            'fields': ('content', 'attachment', 'attachment_name', 'attachment_size')
        }),
        ('Reply', {
            'fields': ('reply_to',)
        }),
        ('Status', {
            'fields': ('is_read', 'is_edited', 'is_deleted')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'read_at'),
            'classes': ('collapse',)
        }),
    )
    
    def content_preview(self, obj):
        """Show preview of message content."""
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'


@admin.register(TypingIndicator)
class TypingIndicatorAdmin(admin.ModelAdmin):
    """Admin interface for TypingIndicator model."""
    list_display = ['id', 'conversation', 'user', 'started_at']
    list_filter = ['started_at']
    search_fields = ['conversation__id', 'user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['id', 'started_at']
    raw_id_fields = ['conversation', 'user']
    date_hierarchy = 'started_at'


@admin.register(MessageReaction)
class MessageReactionAdmin(admin.ModelAdmin):
    """Admin interface for MessageReaction model."""
    list_display = ['id', 'message', 'user', 'reaction_type', 'created_at']
    list_filter = ['reaction_type', 'created_at']
    search_fields = ['message__id', 'user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['id', 'created_at']
    raw_id_fields = ['message', 'user']
    date_hierarchy = 'created_at'


@admin.register(ConversationMute)
class ConversationMuteAdmin(admin.ModelAdmin):
    """Admin interface for ConversationMute model."""
    list_display = ['id', 'conversation', 'user', 'muted_until', 'created_at']
    list_filter = ['created_at', 'muted_until']
    search_fields = ['conversation__id', 'user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['id', 'created_at']
    raw_id_fields = ['conversation', 'user']
    date_hierarchy = 'created_at'


@admin.register(MessageReport)
class MessageReportAdmin(admin.ModelAdmin):
    """Admin interface for MessageReport model."""
    list_display = ['id', 'message', 'reported_by', 'reason', 'status', 'created_at', 'reviewed_at']
    list_filter = ['reason', 'status', 'created_at', 'reviewed_at']
    search_fields = ['message__id', 'reported_by__email', 'description']
    readonly_fields = ['id', 'created_at', 'reviewed_at']
    raw_id_fields = ['message', 'reported_by', 'reviewed_by']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Report Information', {
            'fields': ('id', 'message', 'reported_by', 'reason', 'description')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Admin Review', {
            'fields': ('reviewed_by', 'admin_notes', 'reviewed_at')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_reviewed', 'mark_as_action_taken', 'mark_as_dismissed']
    
    def mark_as_reviewed(self, request, queryset):
        """Mark selected reports as reviewed."""
        from django.utils import timezone
        queryset.update(status='reviewed', reviewed_by=request.user, reviewed_at=timezone.now())
    mark_as_reviewed.short_description = "Mark selected reports as reviewed"
    
    def mark_as_action_taken(self, request, queryset):
        """Mark selected reports as action taken."""
        from django.utils import timezone
        queryset.update(status='action_taken', reviewed_by=request.user, reviewed_at=timezone.now())
    mark_as_action_taken.short_description = "Mark selected reports as action taken"
    
    def mark_as_dismissed(self, request, queryset):
        """Mark selected reports as dismissed."""
        from django.utils import timezone
        queryset.update(status='dismissed', reviewed_by=request.user, reviewed_at=timezone.now())
    mark_as_dismissed.short_description = "Mark selected reports as dismissed"
