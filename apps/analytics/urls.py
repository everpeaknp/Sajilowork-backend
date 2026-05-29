"""
URL routing for Analytics app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    EventViewSet, MetricViewSet, FunnelViewSet,
    FunnelStepViewSet, CohortViewSet, ReportViewSet
)

router = DefaultRouter()
router.register(r'events', EventViewSet, basename='event')
router.register(r'metrics', MetricViewSet, basename='metric')
router.register(r'funnels', FunnelViewSet, basename='funnel')
router.register(r'funnel-steps', FunnelStepViewSet, basename='funnel-step')
router.register(r'cohorts', CohortViewSet, basename='cohort')
router.register(r'reports', ReportViewSet, basename='report')

urlpatterns = [
    path('', include(router.urls)),
]
