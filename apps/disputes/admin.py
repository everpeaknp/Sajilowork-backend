from django.contrib import admin

from .models import Dispute, DisputeEvidence, DisputeMessage


class DisputeEvidenceInline(admin.TabularInline):
    model = DisputeEvidence
    extra = 0
    readonly_fields = ['uploaded_at']


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = ['title', 'task', 'status', 'dispute_type', 'raised_by', 'created_at']
    list_filter = ['status', 'dispute_type']
    search_fields = ['title', 'task__title']
    inlines = [DisputeEvidenceInline]
    readonly_fields = ['created_at', 'updated_at', 'resolved_at']


@admin.register(DisputeMessage)
class DisputeMessageAdmin(admin.ModelAdmin):
    list_display = ['dispute', 'sender', 'created_at']
    list_filter = ['created_at']
