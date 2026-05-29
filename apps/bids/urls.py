"""
URL routing for Bids app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BidViewSet,
    BidMessageViewSet,
    BidReviewViewSet,
    BidNotificationViewSet,
)

app_name = 'bids'

router = DefaultRouter()
router.register(r'bids', BidViewSet, basename='bid')
router.register(r'bid-messages', BidMessageViewSet, basename='bid-message')
router.register(r'bid-reviews', BidReviewViewSet, basename='bid-review')
router.register(r'bid-notifications', BidNotificationViewSet, basename='bid-notification')

urlpatterns = [
    path('', include(router.urls)),
]
