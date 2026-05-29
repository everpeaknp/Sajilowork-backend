"""
Development settings.
"""
from .base import *
import os

DEBUG = True

# Real-time chat (WebSockets) — no Redis required in dev
INSTALLED_APPS = ['daphne', *[app for app in INSTALLED_APPS if app != 'daphne']]
if 'channels' not in INSTALLED_APPS:
    cors_idx = INSTALLED_APPS.index('corsheaders')
    INSTALLED_APPS.insert(cors_idx + 1, 'channels')

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

ALLOWED_HOSTS = ['*']

# Use SQLite for development (no PostgreSQL required)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            # Wait up to 30s when another connection holds the DB (runserver, shell, polling)
            'timeout': 30,
        },
    }
}

# WAL mode allows reads during writes — reduces "database is locked" in local dev
from django.db.backends.signals import connection_created
from django.db.utils import OperationalError

_sqlite_wal_configured = False


def _configure_sqlite(connection, **kwargs):
    global _sqlite_wal_configured
    if connection.vendor != 'sqlite':
        return
    try:
        with connection.cursor() as cursor:
            cursor.execute('PRAGMA busy_timeout=30000;')
            if not _sqlite_wal_configured:
                cursor.execute('PRAGMA journal_mode=WAL;')
                cursor.execute('PRAGMA synchronous=NORMAL;')
                _sqlite_wal_configured = True
    except OperationalError:
        # Another process holds the DB; connection still works with default journal mode
        pass


connection_created.connect(_configure_sqlite)

# Celery — run tasks inline without Redis in local dev
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = False

# Use simple cache backend for development (no Redis required)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# CORS - Allow all origins in development
CORS_ALLOW_ALL_ORIGINS = True

# Email - Console backend for development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Static files - Use default storage for development (no whitenoise compression)
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# Disable security features in development
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Disable throttling in development - avoids hitting rate limits during testing
REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = []
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
    'anon': '100000/hour',  # Very high limit for development
    'user': '100000/hour',  # Very high limit for development
    'burst': '10000/minute',  # Very high burst limit for development
}

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
}


# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
}
