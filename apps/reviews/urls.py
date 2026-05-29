"""Review API routes."""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import ReviewCreateAPIView, ReviewViewSet, UserReviewsAPIView

app_name = 'reviews'

router = DefaultRouter()
router.register(r'', ReviewViewSet, basename='review')

urlpatterns = [
    path('create/', ReviewCreateAPIView.as_view(), name='review-create'),
    path('user/<uuid:user_id>/', UserReviewsAPIView.as_view(), name='user-reviews'),
    path('', include(router.urls)),
]
