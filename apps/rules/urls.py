from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PlatformRuleViewSet, RulePolicyViewSet

app_name = 'rules'

router = DefaultRouter()
router.register(r'policies', RulePolicyViewSet, basename='rule-policies')
router.register(r'legacy', PlatformRuleViewSet, basename='platform-rules')
# Backward-compatible root (legacy moderation list)
router.register(r'', PlatformRuleViewSet, basename='rules-root')

urlpatterns = [
    path('', include(router.urls)),
]
