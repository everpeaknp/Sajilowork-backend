"""
URL configuration for accounts app (JWT authentication).
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

app_name = 'accounts'

urlpatterns = [
    # JWT Token endpoints
    path('token/', views.CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', views.verify_token_view, name='token_verify'),
    
    # Authentication endpoints
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Password management
    path('password/reset/', views.password_reset_request_view, name='password_reset_request'),
    path('password/reset/confirm/', views.password_reset_confirm_view, name='password_reset_confirm'),
    path('password/change/', views.change_password_view, name='change_password'),
    
    # Email verification
    path('email/verify/', views.verify_email_view, name='verify_email'),

    # Social OAuth (browser redirect flow)
    path('google/login/', views.google_login_view, name='google_login'),
    path('google/callback/', views.google_callback_view, name='google_callback'),
    path('facebook/login/', views.facebook_login_view, name='facebook_login'),
    path('facebook/callback/', views.facebook_callback_view, name='facebook_callback'),
]
