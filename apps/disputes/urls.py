from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DisputeViewSet

app_name = 'disputes'

router = DefaultRouter()
router.register(r'', DisputeViewSet, basename='disputes')

urlpatterns = [
    path('', include(router.urls)),
]
