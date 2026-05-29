"""
Custom Django admin views for platform business analytics.
"""
from django.contrib import admin
from django.shortcuts import render

from .business_metrics import BusinessMetricsService

PERIOD_CHOICES = (
    (7, '7 days'),
    (30, '30 days'),
    (90, '90 days'),
    (365, '1 year'),
    (0, 'All time'),
)


def business_analytics_dashboard(request):
    """Full business analytics dashboard at /admin/analytics/."""
    raw = request.GET.get('days', '30')
    try:
        days = int(raw)
    except (TypeError, ValueError):
        days = 30
    period_days = None if days == 0 else days

    report = BusinessMetricsService.get_dashboard(period_days=period_days)

    context = {
        **admin.site.each_context(request),
        'title': 'Business analytics',
        'report': report,
        'period_choices': PERIOD_CHOICES,
        'selected_days': days if days != 0 else 0,
        'opts': {'app_label': 'analytics', 'model_name': 'metric'},
    }
    return render(request, 'admin/analytics/business_dashboard.html', context)
