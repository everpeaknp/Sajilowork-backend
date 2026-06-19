"""
Uploads URLs
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UploadViewSet, ImageUploadViewSet, DocumentUploadViewSet,
    UploadQuotaViewSet
)
from .cloudinary_views import CloudinaryConfigView, CloudinaryUploadView

router = DefaultRouter()
router.register(r'uploads', UploadViewSet, basename='upload')
router.register(r'images', ImageUploadViewSet, basename='image-upload')
router.register(r'documents', DocumentUploadViewSet, basename='document-upload')
router.register(r'quotas', UploadQuotaViewSet, basename='upload-quota')

urlpatterns = [
    path('cloudinary-config/', CloudinaryConfigView.as_view(), name='cloudinary-config'),
    path('cloudinary-upload/', CloudinaryUploadView.as_view(), name='cloudinary-upload'),
    path('', include(router.urls)),
]
