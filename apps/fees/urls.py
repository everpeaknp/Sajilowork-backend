from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import FeeCalculateViewSet, FeeRuleViewSet

app_name = 'fees'

router = DefaultRouter()
router.register(r'', FeeCalculateViewSet, basename='fee-calculate')
router.register(r'rules', FeeRuleViewSet, basename='fee-rules')

urlpatterns = [
    path('', include(router.urls)),
]
