"""
Dashboard URL Configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import DashboardViewSet

app_name = 'dashboard'

router = DefaultRouter()
router.register(r'', DashboardViewSet, basename='dashboard')

urlpatterns = [
    path('', include(router.urls)),
]
