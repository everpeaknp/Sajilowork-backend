"""
Uploads Models
Handles file uploads, image processing, and document management.
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext_lazy as _
import uuid
import os

User = get_user_model()


class Upload(models.Model):
    """
    Base upload model for all file types.
    Uses generic relations to link to any model.
    """
    FILE_TYPE_CHOICES = [
        ('image', 'Image'),
        ('document', 'Document'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='uploads'
    )
    
    # Generic relation to any model
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    object_id = models.UUIDField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # File information
    file = models.FileField(upload_to='sajilowork/uploads/%Y/%m/%d/')
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES)
    file_size = models.BigIntegerField(help_text="File size in bytes")
    mime_type = models.CharField(max_length=100)
    
    # Processing status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    
    # Metadata
    is_public = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'uploads'
        verbose_name = _('Upload')
        verbose_name_plural = _('Uploads')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['file_type', 'status']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.file_name} - {self.user.email}"
    
    @property
    def file_extension(self):
        """Get file extension"""
        return os.path.splitext(self.file_name)[1].lower()
    
    @property
    def file_size_mb(self):
        """Get file size in MB"""
        return round(self.file_size / (1024 * 1024), 2)
    
    def delete(self, *args, **kwargs):
        """Delete file from storage when model is deleted"""
        if self.file:
            self.file.delete(save=False)
        super().delete(*args, **kwargs)


class ImageUpload(models.Model):
    """
    Image-specific upload model with dimensions and thumbnails.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    upload = models.OneToOneField(
        Upload,
        on_delete=models.CASCADE,
        related_name='image_data'
    )
    
    # Image dimensions
    width = models.IntegerField()
    height = models.IntegerField()
    
    # Thumbnails (generated if Pillow is available)
    thumbnail_small = models.ImageField(
        upload_to='sajilowork/thumbnails/small/%Y/%m/%d/',
        null=True,
        blank=True,
        help_text="150x150 thumbnail"
    )
    thumbnail_medium = models.ImageField(
        upload_to='sajilowork/thumbnails/medium/%Y/%m/%d/',
        null=True,
        blank=True,
        help_text="300x300 thumbnail"
    )
    thumbnail_large = models.ImageField(
        upload_to='sajilowork/thumbnails/large/%Y/%m/%d/',
        null=True,
        blank=True,
        help_text="600x600 thumbnail"
    )
    
    # Image metadata
    format = models.CharField(max_length=10, blank=True)
    color_mode = models.CharField(max_length=20, blank=True)
    has_transparency = models.BooleanField(default=False)
    
    # Processing flags
    is_optimized = models.BooleanField(default=False)
    thumbnails_generated = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'image_uploads'
        verbose_name = _('Image Upload')
        verbose_name_plural = _('Image Uploads')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Image: {self.upload.file_name} ({self.width}x{self.height})"
    
    @property
    def aspect_ratio(self):
        """Calculate aspect ratio"""
        if self.height > 0:
            return round(self.width / self.height, 2)
        return 0
    
    def delete(self, *args, **kwargs):
        """Delete thumbnail files when model is deleted"""
        if self.thumbnail_small:
            self.thumbnail_small.delete(save=False)
        if self.thumbnail_medium:
            self.thumbnail_medium.delete(save=False)
        if self.thumbnail_large:
            self.thumbnail_large.delete(save=False)
        super().delete(*args, **kwargs)


class DocumentUpload(models.Model):
    """
    Document-specific upload model with page count and text extraction.
    """
    DOCUMENT_TYPE_CHOICES = [
        ('pdf', 'PDF'),
        ('doc', 'Word Document'),
        ('docx', 'Word Document (DOCX)'),
        ('xls', 'Excel Spreadsheet'),
        ('xlsx', 'Excel Spreadsheet (XLSX)'),
        ('ppt', 'PowerPoint Presentation'),
        ('pptx', 'PowerPoint Presentation (PPTX)'),
        ('txt', 'Text File'),
        ('csv', 'CSV File'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    upload = models.OneToOneField(
        Upload,
        on_delete=models.CASCADE,
        related_name='document_data'
    )
    
    # Document metadata
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES)
    page_count = models.IntegerField(null=True, blank=True)
    word_count = models.IntegerField(null=True, blank=True)
    
    # Text extraction
    extracted_text = models.TextField(blank=True, help_text="Extracted text content")
    text_extracted = models.BooleanField(default=False)
    
    # Document properties
    title = models.CharField(max_length=255, blank=True)
    author = models.CharField(max_length=255, blank=True)
    created_date = models.DateTimeField(null=True, blank=True)
    modified_date = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'document_uploads'
        verbose_name = _('Document Upload')
        verbose_name_plural = _('Document Uploads')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Document: {self.upload.file_name} ({self.document_type})"


class UploadQuota(models.Model):
    """
    Track upload quotas per user.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='upload_quota'
    )
    
    # Quota limits (in bytes)
    total_quota = models.BigIntegerField(
        default=1073741824,  # 1GB default
        help_text="Total storage quota in bytes"
    )
    used_quota = models.BigIntegerField(
        default=0,
        help_text="Used storage in bytes"
    )
    
    # File count limits
    max_files = models.IntegerField(
        default=1000,
        help_text="Maximum number of files"
    )
    file_count = models.IntegerField(
        default=0,
        help_text="Current number of files"
    )
    
    # Reset tracking
    last_reset = models.DateTimeField(auto_now_add=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'upload_quotas'
        verbose_name = _('Upload Quota')
        verbose_name_plural = _('Upload Quotas')
    
    def __str__(self):
        return f"{self.user.email} - {self.used_quota_mb}/{self.total_quota_mb} MB"
    
    @property
    def used_quota_mb(self):
        """Get used quota in MB"""
        return round(self.used_quota / (1024 * 1024), 2)
    
    @property
    def total_quota_mb(self):
        """Get total quota in MB"""
        return round(self.total_quota / (1024 * 1024), 2)
    
    @property
    def remaining_quota(self):
        """Get remaining quota in bytes"""
        return max(0, self.total_quota - self.used_quota)
    
    @property
    def remaining_quota_mb(self):
        """Get remaining quota in MB"""
        return round(self.remaining_quota / (1024 * 1024), 2)
    
    @property
    def quota_percentage(self):
        """Get quota usage percentage"""
        if self.total_quota > 0:
            return round((self.used_quota / self.total_quota) * 100, 2)
        return 0
    
    def has_quota(self, file_size):
        """Check if user has enough quota for file"""
        return (self.remaining_quota >= file_size and 
                self.file_count < self.max_files)
    
    def add_file(self, file_size):
        """Add file to quota"""
        self.used_quota += file_size
        self.file_count += 1
        self.save()
    
    def remove_file(self, file_size):
        """Remove file from quota"""
        self.used_quota = max(0, self.used_quota - file_size)
        self.file_count = max(0, self.file_count - 1)
        self.save()
