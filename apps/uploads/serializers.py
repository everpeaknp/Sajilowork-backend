"""
Uploads Serializers
"""
from rest_framework import serializers
from .models import Upload, ImageUpload, DocumentUpload, UploadQuota


class UploadSerializer(serializers.ModelSerializer):
    """Serializer for Upload model"""
    
    file_extension = serializers.CharField(read_only=True)
    file_size_mb = serializers.FloatField(read_only=True)
    file_type_display = serializers.CharField(source='get_file_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = Upload
        fields = [
            'id', 'user', 'user_email', 'file', 'file_name', 'file_type',
            'file_type_display', 'file_size', 'file_size_mb', 'file_extension',
            'mime_type', 'status', 'status_display', 'error_message',
            'is_public', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'file_size', 'mime_type', 'status',
            'error_message', 'created_at', 'updated_at'
        ]


class UploadCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating uploads"""
    
    class Meta:
        model = Upload
        fields = ['file', 'file_type', 'is_public']
    
    def validate_file(self, value):
        """Validate file size and type"""
        # Max file size: 10MB
        max_size = 10 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError(
                f"File size exceeds maximum allowed size of {max_size / (1024 * 1024)}MB."
            )
        
        return value
    
    def create(self, validated_data):
        """Create upload with metadata"""
        file = validated_data['file']
        
        # Extract file metadata
        validated_data['file_name'] = file.name
        validated_data['file_size'] = file.size
        validated_data['mime_type'] = file.content_type or 'application/octet-stream'
        
        return super().create(validated_data)


class ImageUploadSerializer(serializers.ModelSerializer):
    """Serializer for ImageUpload model"""
    
    upload = UploadSerializer(read_only=True)
    aspect_ratio = serializers.FloatField(read_only=True)
    
    class Meta:
        model = ImageUpload
        fields = [
            'id', 'upload', 'width', 'height', 'aspect_ratio',
            'thumbnail_small', 'thumbnail_medium', 'thumbnail_large',
            'format', 'color_mode', 'has_transparency',
            'is_optimized', 'thumbnails_generated',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields


class DocumentUploadSerializer(serializers.ModelSerializer):
    """Serializer for DocumentUpload model"""
    
    upload = UploadSerializer(read_only=True)
    document_type_display = serializers.CharField(source='get_document_type_display', read_only=True)
    
    class Meta:
        model = DocumentUpload
        fields = [
            'id', 'upload', 'document_type', 'document_type_display',
            'page_count', 'word_count', 'extracted_text', 'text_extracted',
            'title', 'author', 'created_date', 'modified_date',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields


class UploadQuotaSerializer(serializers.ModelSerializer):
    """Serializer for UploadQuota model"""
    
    used_quota_mb = serializers.FloatField(read_only=True)
    total_quota_mb = serializers.FloatField(read_only=True)
    remaining_quota_mb = serializers.FloatField(read_only=True)
    quota_percentage = serializers.FloatField(read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = UploadQuota
        fields = [
            'id', 'user', 'user_email', 'total_quota', 'total_quota_mb',
            'used_quota', 'used_quota_mb', 'remaining_quota_mb',
            'quota_percentage', 'max_files', 'file_count',
            'last_reset', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'used_quota', 'file_count',
            'last_reset', 'created_at', 'updated_at'
        ]


class UploadListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for upload lists"""
    
    file_size_mb = serializers.FloatField(read_only=True)
    file_type_display = serializers.CharField(source='get_file_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Upload
        fields = [
            'id', 'file_name', 'file_type', 'file_type_display',
            'file_size_mb', 'status', 'status_display',
            'is_public', 'created_at'
        ]
        read_only_fields = fields


class UploadStatsSerializer(serializers.Serializer):
    """Serializer for upload statistics"""
    
    total_uploads = serializers.IntegerField()
    total_size_mb = serializers.FloatField()
    uploads_by_type = serializers.DictField()
    uploads_by_status = serializers.DictField()
    recent_uploads = UploadListSerializer(many=True)


class QuotaCheckRequestSerializer(serializers.Serializer):
    """Serializer for quota check request"""
    
    file_size = serializers.IntegerField(min_value=1)


class QuotaCheckResponseSerializer(serializers.Serializer):
    """Serializer for quota check response"""
    
    has_quota = serializers.BooleanField()
    remaining_quota_mb = serializers.FloatField()
    quota_percentage = serializers.FloatField()
    message = serializers.CharField()
