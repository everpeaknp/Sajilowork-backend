"""
Production settings.
"""
from .base import *

DEBUG = False

# Security
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Explicit origins only — never allow all origins with credentials enabled.
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='https://www.sajilowork.com,https://sajilowork.com,https://sajilowork.everacy.com,http://localhost:3000,http://127.0.0.1:3000',
    cast=Csv(),
)

# WebSockets (Daphne entrypoint) require channels when Redis is available.
if config('REDIS_URL', default=''):
    INSTALLED_APPS = ['daphne', *[app for app in INSTALLED_APPS if app != 'daphne']]
    if 'channels' not in INSTALLED_APPS:
        cors_idx = INSTALLED_APPS.index('corsheaders')
        INSTALLED_APPS.insert(cors_idx + 1, 'channels')

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

import dj_database_url

if config('DATABASE_URL', default=None):
    DATABASES = {
        'default': dj_database_url.config(
            default=config('DATABASE_URL'),
            conn_max_age=600,
            conn_health_checks=True,
        )
    }

if not config('REDIS_URL', default=''):
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }

# Production defaults — override localhost fallbacks from base when env vars are missing.
FRONTEND_URL = config('FRONTEND_URL', default='https://www.sajilowork.com')
BACKEND_URL = config('BACKEND_URL', default='https://sajiloworkbackend.everacy.com')
GOOGLE_OAUTH_REDIRECT_URI = config(
    'GOOGLE_OAUTH_REDIRECT_URI',
    default='https://sajiloworkbackend.everacy.com/api/v1/auth/google/callback/',
)

# Production static files — use WhiteNoise without manifest hashing so admin
# CSS/JS cannot 404 when the manifest is missing or out of date.
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
WHITENOISE_USE_FINDERS = False
WHITENOISE_AUTOREFRESH = False
SENTRY_DSN = config('SENTRY_DSN', default='')
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=config('SENTRY_TRACES_SAMPLE_RATE', default=0.1, cast=float),
        send_default_pii=False,
        environment=config('SENTRY_ENVIRONMENT', default='production'),
    )

