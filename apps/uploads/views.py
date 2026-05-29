"""
Uploads Views
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count

from .models import Upload, ImageUpload, DocumentUpload, UploadQuota
from .serializers import (
    UploadSerializer, UploadCreateSerializer, UploadListSerializer,
    ImageUploadSerializer, DocumentUploadSerializer,
    UploadQuotaSerializer, UploadStatsSerializer,
    QuotaCheckRequestSerializer, QuotaCheckResponseSerializer
)
from .permissions import IsOwnerOrReadOnly
from .services import UploadService


class UploadViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Upload CRUD operations.
    """
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['file_type', 'status', 'is_public', 'is_active']
    search_fields = ['file_name', 'mime_type']
    ordering_fields = ['created_at', 'file_size', 'file_name']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return uploads for current user"""
        return Upload.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        """Return appropriate serializer class"""
        if self.action == 'list':
            return UploadListSerializer
        elif self.action == 'create':
            return UploadCreateSerializer
        return UploadSerializer
    
    def perform_create(self, serializer):
        """Create upload for current user"""
        # Check quota
        quota, created = UploadQuota.objects.get_or_create(user=self.request.user)
        
        file_size = serializer.validated_data['file'].size
        if not quota.has_quota(file_size):
            from rest_framework.exceptions import ValidationError
            raise ValidationError({
                'file': 'Upload quota exceeded. Please delete some files or upgrade your plan.'
            })
        
        # Save upload
        upload = serializer.save(user=self.request.user)
        
        # Update quota
        quota.add_file(file_size)
        
        # Process upload asynchronously (if Celery is available)
        # UploadService.process_upload(upload.id)
    
    def perform_destroy(self, instance):
        """Delete upload and update quota"""
        # Update quota
        quota = UploadQuota.objects.get(user=self.request.user)
        quota.remove_file(instance.file_size)
        
        # Delete upload
        instance.delete()
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get upload statistics for current user"""
        uploads = self.get_queryset()
        
        stats = {
            'total_uploads': uploads.count(),
            'total_size_mb': round(
                (uploads.aggregate(Sum('file_size'))['file_size__sum'] or 0) / (1024 * 1024),
                2
            ),
            'uploads_by_type': dict(
                uploads.values('file_type').annotate(count=Count('id')).values_list('file_type', 'count')
            ),
            'uploads_by_status': dict(
                uploads.values('status').annotate(count=Count('id')).values_list('status', 'count')
            ),
            'recent_uploads': uploads[:10]
        }
        
        serializer = UploadStatsSerializer(stats)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def images(self, request):
        """Get all image uploads"""
        uploads = self.get_queryset().filter(file_type='image')
        
        page = self.paginate_queryset(uploads)
        if page is not None:
            serializer = UploadListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = UploadListSerializer(uploads, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def documents(self, request):
        """Get all document uploads"""
        uploads = self.get_queryset().filter(file_type='document')
        
        page = self.paginate_queryset(uploads)
        if page is not None:
            serializer = UploadListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = UploadListSerializer(uploads, many=True)
        return Response(serializer.data)


class ImageUploadViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for ImageUpload (read-only).
    """
    serializer_class = ImageUploadSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'width', 'height']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return image uploads for current user"""
        return ImageUpload.objects.filter(
            upload__user=self.request.user
        ).select_related('upload')


class DocumentUploadViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for DocumentUpload (read-only).
    """
    serializer_class = DocumentUploadSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['document_type', 'text_extracted']
    ordering_fields = ['created_at', 'page_count', 'word_count']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return document uploads for current user"""
        return DocumentUpload.objects.filter(
            upload__user=self.request.user
        ).select_related('upload')


class UploadQuotaViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for UploadQuota (read-only).
    """
    serializer_class = UploadQuotaSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return quota for current user"""
        return UploadQuota.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def my_quota(self, request):
        """Get current user's quota"""
        quota, created = UploadQuota.objects.get_or_create(user=request.user)
        serializer = UploadQuotaSerializer(quota)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def check_quota(self, request):
        """Check if user has enough quota for a file"""
        serializer = QuotaCheckRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        file_size = serializer.validated_data['file_size']
        quota, created = UploadQuota.objects.get_or_create(user=request.user)
        
        has_quota = quota.has_quota(file_size)
        
        response_data = {
            'has_quota': has_quota,
            'remaining_quota_mb': quota.remaining_quota_mb,
            'quota_percentage': quota.quota_percentage,
            'message': 'Sufficient quota available.' if has_quota else 'Quota exceeded.'
        }
        
        response_serializer = QuotaCheckResponseSerializer(response_data)
        return Response(response_serializer.data)
