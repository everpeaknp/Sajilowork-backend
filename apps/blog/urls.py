from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BlogPostViewSet

app_name = 'blog'

router = DefaultRouter()
router.register(r'posts', BlogPostViewSet, basename='blog-post')

urlpatterns = [
    path('', include(router.urls)),
]
