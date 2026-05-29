"""
URL configuration for airtasker project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

from apps.analytics.admin_views import business_analytics_dashboard
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    # Platform business analytics (staff only)
    path(
        'admin/analytics/',
        admin.site.admin_view(business_analytics_dashboard),
        name='admin-business-analytics',
    ),
    # Shortcut into rules policies on the main admin (full sidebar with all apps)
    path(
        'admin/rules/',
        RedirectView.as_view(url='/admin/rules/rulepolicy/', permanent=False),
        name='admin-rules-home',
    ),
    path('admin/', admin.site.urls),

    # API documentation (OpenAPI 3 — Swagger UI + ReDoc)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # API v1 - Only enabled apps
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/users/', include('apps.users.urls')),
    path('api/v1/tasks/', include('apps.tasks.urls')),
    path('api/v1/bids/', include('apps.bids.urls')),
    path('api/v1/reviews/', include('apps.reviews.urls')),
    path('api/v1/chat/', include('apps.chat.urls')),
    path('api/v1/notifications/', include('apps.notifications.urls')),
    path('api/v1/payments/', include('apps.payments.urls')),
    path('api/v1/fees/', include('apps.fees.urls')),
    path('api/v1/rules/', include('apps.rules.urls')),
    path('api/v1/disputes/', include('apps.disputes.urls')),
    path('api/v1/wallets/', include('apps.wallets.urls')),
    path('api/v1/dashboard/', include('apps.dashboard.urls')),
    path('api/v1/search/', include('apps.search.urls')),
    path('api/v1/locations/', include('apps.locations.urls')),
    path('api/v1/uploads/', include('apps.uploads.urls')),
    path('api/v1/analytics/', include('apps.analytics.urls')),
    path('api/v1/blog/', include('apps.blog.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
