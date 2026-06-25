"""
URL configuration for airtasker project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

from apps.analytics.admin_views import business_analytics_dashboard
from apps.faq.views import FaqListAPIView
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
    path(
        'admin/category/',
        RedirectView.as_view(url='/admin/category/category/', permanent=False),
        name='admin-category-home',
    ),
    path(
        'admin/skills/',
        RedirectView.as_view(url='/admin/skills/skill/', permanent=False),
        name='admin-skills-home',
    ),
    path(
        'admin/language/',
        RedirectView.as_view(url='/admin/language/locale/', permanent=False),
        name='admin-language-home',
    ),
    path(
        'admin/bookmark/',
        RedirectView.as_view(url='/admin/bookmark/bookmark/', permanent=False),
        name='admin-bookmark-home',
    ),
    path('admin/', admin.site.urls),

    # API documentation (OpenAPI 3 — Swagger UI + ReDoc)
    # Core schema used by all documentation frontends.
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    # Primary Swagger UI used by engineers and the Next.js team.
    path(
        'api/docs/',
        SpectacularSwaggerView.as_view(url_name='schema'),
        name='swagger-ui',
    ),
    # Branded Swagger UI entrypoint for business / product stakeholders.
    # This simply reuses the same OpenAPI schema, but lets you apply a
    # custom favicon / title / CSS if desired.
    path(
        'api/docs/tasknepal/',
        SpectacularSwaggerView.as_view(url_name='schema'),
        name='swagger-ui-tasknepal',
    ),
    # Read‑only, text‑focused reference.
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # API v1 - Only enabled apps
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/users/', include('apps.users.urls')),
    path('api/v1/employers/', include('apps.users.employer_urls')),
    path('api/v1/freelancers/', include('apps.users.freelancer_urls')),
    path('api/v1/tasks/', include('apps.tasks.urls')),
    path('api/v1/bookmarks/', include('apps.bookmark.urls')),
    path('api/v1/skills/', include('apps.skills.urls')),
    path('api/v1/languages/', include('apps.language.urls')),
    path('api/v1/services/', include('apps.services.urls')),
    path('api/v1/projects/', include('apps.projects.urls')),
    path('api/v1/jobs/', include('apps.jobs.urls')),
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
    path('api/v1/faq/', FaqListAPIView.as_view(), name='api-faq-list'),
    path('api/v1/site/', include('apps.site_branding.urls')),
    
    # Admin-only endpoints
    path('api/admin/mails/', include('apps.mails.urls')),  # Email Management System
    
    path('faq/', FaqListAPIView.as_view(), name='faq-list'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
