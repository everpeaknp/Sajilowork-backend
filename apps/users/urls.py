"""
URL routing for Users app.

All URLs here are mounted under /api/v1/users/ in config/urls.py.

Frontend expects:
  GET/PATCH  /api/v1/users/me/
  GET        /api/v1/users/me/skills/
  POST       /api/v1/users/me/skills/
  PATCH      /api/v1/users/me/skills/<id>/
  DELETE     /api/v1/users/me/skills/<id>/
  GET/POST   /api/v1/users/me/badges/
  GET        /api/v1/users/me/portfolio/
  POST       /api/v1/users/me/portfolio/
  DELETE     /api/v1/users/me/portfolio/<id>/
  POST       /api/v1/users/me/upload-image/
  POST       /api/v1/users/me/change-password/
  GET        /api/v1/users/stats/
  GET        /api/v1/users/taskers/
  GET        /api/v1/users/<pk>/
  GET        /api/v1/users/<pk>/public_profile/
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, UserSkillViewSet, UserBadgeViewSet, UserDocumentViewSet,
    UserRegistrationView, PasswordResetRequestView, PasswordResetConfirmView,
    EmailVerificationView, PortfolioView, PortfolioDetailView
)

app_name = 'users'

# Register UserViewSet at '' so it maps to /api/v1/users/<pk>/ etc.
router = DefaultRouter()
router.register(r'', UserViewSet, basename='user')

urlpatterns = [
    # ── Auth helpers ──────────────────────────────────────────────────────────
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password-reset'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('verify-email/', EmailVerificationView.as_view(), name='verify-email'),

    # ── Current-user sub-resources (explicit paths, must come before router) ──
    # Portfolio  →  GET/POST  /api/v1/users/me/portfolio/
    path('me/portfolio/', PortfolioView.as_view(), name='my-portfolio'),
    path('me/portfolio/<uuid:id>/', PortfolioDetailView.as_view(), name='portfolio-detail'),

    # Skills  →  GET/POST  /api/v1/users/me/skills/
    path('me/skills/', UserSkillViewSet.as_view({'get': 'list', 'post': 'create'}), name='my-skills'),
    path('me/skills/<pk>/', UserSkillViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'delete': 'destroy'}), name='my-skill-detail'),

    # Badges  →  GET/POST  /api/v1/users/me/badges/
    path('me/badges/', UserBadgeViewSet.as_view({'get': 'list', 'post': 'create'}), name='my-badges'),

    # Documents  →  GET/POST  /api/v1/users/me/documents/
    path('me/documents/', UserDocumentViewSet.as_view({'get': 'list', 'post': 'create'}), name='my-documents'),
    path('me/documents/<pk>/', UserDocumentViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'delete': 'destroy'}), name='my-document-detail'),

    # ── Router URLs (UserViewSet: me, stats, taskers, <pk>/, etc.) ────────────
    path('', include(router.urls)),
]
