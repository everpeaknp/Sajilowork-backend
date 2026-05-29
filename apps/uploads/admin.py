"""
Uploads Admin
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Upload, ImageUpload, DocumentUpload, UploadQuota


@admin.register(Upload)
class UploadAdmin(admin.ModelAdmin):
    """Admin interface for Upload model"""
    
    list_display = [
        'file_name', 'user_email', 'file_type', 'file_size_display',
        'status_badge', 'is_public', 'created_at'
    ]
    list_filter = ['file_type', 'status', 'is_public', 'is_active', 'created_at']
    search_fields = ['file_name', 'user__email', 'mime_type']
    readonly_fields = [
        'id', 'file_size', 'mime_type', 'file_extension',
        'created_at', 'updated_at'
    ]
    fieldsets = (
        ('File Information', {
            'fields': ('id', 'user', 'file', 'file_name', 'file_type', 
                      'file_size', 'mime_type', 'file_extension')
        }),
        ('Status', {
            'fields': ('status', 'error_message')
        }),
        ('Settings', {
            'fields': ('is_public', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    
    def file_size_display(self, obj):
        return f"{obj.file_size_mb} MB"
    file_size_display.short_description = 'File Size'
    
    def status_badge(self, obj):
        colors = {
            'pending': '#FFA500',
            'processing': '#007BFF',
            'completed': '#28A745',
            'failed': '#DC3545',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, '#6C757D'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(ImageUpload)
class ImageUploadAdmin(admin.ModelAdmin):
    """Admin interface for ImageUpload model"""
    
    list_display = [
        'upload_file_name', 'dimensions', 'format', 'thumbnails_status',
        'created_at'
    ]
    list_filter = ['format', 'has_transparency', 'thumbnails_generated', 'created_at']
    search_fields = ['upload__file_name', 'upload__user__email']
    readonly_fields = [
        'id', 'width', 'height', 'aspect_ratio', 'format', 'color_mode',
        'has_transparency', 'created_at', 'updated_at'
    ]
    fieldsets = (
        ('Upload', {
            'fields': ('id', 'upload')
        }),
        ('Image Properties', {
            'fields': ('width', 'height', 'aspect_ratio', 'format', 
                      'color_mode', 'has_transparency')
        }),
        ('Thumbnails', {
            'fields': ('thumbnail_small', 'thumbnail_medium', 'thumbnail_large',
                      'thumbnails_generated')
        }),
        ('Processing', {
            'fields': ('is_optimized',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def upload_file_name(self, obj):
        return obj.upload.file_name
    upload_file_name.short_description = 'File Name'
    
    def dimensions(self, obj):
        return f"{obj.width}x{obj.height}"
    dimensions.short_description = 'Dimensions'
    
    def thumbnails_status(self, obj):
        if obj.thumbnails_generated:
            return format_html(
                '<span style="color: green;">✓ Generated</span>'
            )
        return format_html(
            '<span style="color: orange;">⏳ Pending</span>'
        )
    thumbnails_status.short_description = 'Thumbnails'


@admin.register(DocumentUpload)
class DocumentUploadAdmin(admin.ModelAdmin):
    """Admin interface for DocumentUpload model"""
    
    list_display = [
        'upload_file_name', 'document_type', 'page_count', 'word_count',
        'text_extracted', 'created_at'
    ]
    list_filter = ['document_type', 'text_extracted', 'created_at']
    search_fields = ['upload__file_name', 'upload__user__email', 'title', 'author']
    readonly_fields = [
        'id', 'page_count', 'word_count', 'extracted_text',
        'created_at', 'updated_at'
    ]
    fieldsets = (
        ('Upload', {
            'fields': ('id', 'upload')
        }),
        ('Document Properties', {
            'fields': ('document_type', 'page_count', 'word_count')
        }),
        ('Metadata', {
            'fields': ('title', 'author', 'created_date', 'modified_date')
        }),
        ('Text Extraction', {
            'fields': ('text_extracted', 'extracted_text')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def upload_file_name(self, obj):
        return obj.upload.file_name
    upload_file_name.short_description = 'File Name'


@admin.register(UploadQuota)
class UploadQuotaAdmin(admin.ModelAdmin):
    """Admin interface for UploadQuota model"""
    
    list_display = [
        'user_email', 'quota_usage', 'file_usage', 'quota_bar',
        'last_reset'
    ]
    list_filter = ['last_reset', 'created_at']
    search_fields = ['user__email']
    readonly_fields = [
        'id', 'used_quota_mb', 'total_quota_mb', 'remaining_quota_mb',
        'quota_percentage', 'created_at', 'updated_at'
    ]
    fieldsets = (
        ('User', {
            'fields': ('id', 'user')
        }),
        ('Storage Quota', {
            'fields': ('total_quota', 'total_quota_mb', 'used_quota', 
                      'used_quota_mb', 'remaining_quota_mb', 'quota_percentage')
        }),
        ('File Count', {
            'fields': ('max_files', 'file_count')
        }),
        ('Reset', {
            'fields': ('last_reset',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    date_hierarchy = 'last_reset'
    ordering = ['-used_quota']
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    
    def quota_usage(self, obj):
        return f"{obj.used_quota_mb}/{obj.total_quota_mb} MB ({obj.quota_percentage}%)"
    quota_usage.short_description = 'Quota Usage'
    
    def file_usage(self, obj):
        return f"{obj.file_count}/{obj.max_files} files"
    file_usage.short_description = 'File Usage'
    
    def quota_bar(self, obj):
        percentage = obj.quota_percentage
        color = '#28A745' if percentage < 70 else '#FFC107' if percentage < 90 else '#DC3545'
        return format_html(
            '<div style="width: 100px; background-color: #E9ECEF; border-radius: 3px;">'
            '<div style="width: {}%; background-color: {}; height: 20px; border-radius: 3px;"></div>'
            '</div>',
            min(percentage, 100),
            color
        )
    quota_bar.short_description = 'Usage'
