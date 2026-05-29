"""
Django base settings for airtasker project.
Production-ready configuration with security best practices.
"""
import os
from pathlib import Path
from datetime import timedelta
from decouple import Config, Csv, RepositoryEnv

# Apply Python 3.14 compatibility patch for Django
# This fixes the 'super' object has no attribute 'dicts' error
# TODO: Remove this patch when upgrading to Python 3.12 or when Django fully supports 3.14
try:
    from config.django_py314_patch import patched_copy
except ImportError:
    pass  # Patch not needed or already applied

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Always load env from backend/.env (not process cwd)
_env_file = BASE_DIR / '.env'
if _env_file.is_file():
    config = Config(RepositoryEnv(str(_env_file)))
else:
    config = Config()

# Security Settings
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-this-in-production')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# Application definition
DJANGO_APPS = [
    # 'daphne',  # ASGI server - commented out until WebSocket apps are ready
    'jazzmin',  # Modern admin theme - MUST be before django.contrib.admin
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    # 'django_filters',
    'drf_spectacular',
    # 'channels',
    # 'django_celery_beat',
    # 'django_celery_results',
    # 'allauth',
    # 'allauth.account',
    # 'allauth.socialaccount',
    # 'phonenumber_field',
    # 'storages',
]

LOCAL_APPS = [
    'apps.accounts',
    'apps.users',
    'apps.tasks',
    'apps.bids',
    'apps.reviews',
    'apps.chat',
    'apps.notifications',
    'apps.payments',
    'apps.fees',
    'apps.rules',
    'apps.disputes',
    'apps.wallets',
    'apps.dashboard',
    'apps.search',
    'apps.locations',
    'apps.uploads',
    'apps.analytics',
    'apps.blog',
    # 'apps.moderation',
    # 'apps.common',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # 'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.rules.middleware.AccountSuspensionMiddleware',
    # 'utils.middleware.RequestLoggingMiddleware',
    # 'utils.middleware.ExceptionHandlerMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='airtasker_db'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD', default='postgres'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'ATOMIC_REQUESTS': True,
        'CONN_MAX_AGE': 600,
        'OPTIONS': {
            'connect_timeout': 10,
        }
    }
}

# Custom User Model
AUTH_USER_MODEL = 'users.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Site ID
SITE_ID = 1

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'burst': '60/minute',
    },
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'utils.exceptions.custom_exception_handler',
    'DATETIME_FORMAT': '%Y-%m-%dT%H:%M:%S.%fZ',
    'DATE_FORMAT': '%Y-%m-%d',
}

# JWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# CORS Configuration
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000,http://127.0.0.1:3000',
    cast=Csv()
)
CORS_ALLOW_CREDENTIALS = True

# Channels Configuration
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [(config('REDIS_HOST', default='localhost'), config('REDIS_PORT', default=6379, cast=int))],
        },
    },
}

# Celery Configuration
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Cache Configuration
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://localhost:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
    }
}

# Email Configuration
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@airtasker.com')

# File Upload Settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# DRF Spectacular — http://localhost:8000/api/docs/
from config.openapi import API_TAGS, load_api_description

SPECTACULAR_SETTINGS = {
    'TITLE': 'tasknepal API',
    'DESCRIPTION': load_api_description(),
    'VERSION': '1.0.0',
    'CONTACT': {
        'name': 'tasknepal Engineering',
        'email': 'support@tasknepal.com',
    },
    'LICENSE': {'name': 'Proprietary'},
    'SERVE_INCLUDE_SCHEMA': False,
    'SCHEMA_PATH_PREFIX': r'/api/v1',
    'SCHEMA_PATH_PREFIX_TRIM': True,
    'COMPONENT_SPLIT_REQUEST': True,
    'SORT_OPERATIONS': True,
    'TAGS': API_TAGS,
    'SERVERS': [
        {'url': 'http://localhost:8000', 'description': 'Local development'},
        {'url': config('API_PUBLIC_URL', default='http://localhost:8000'), 'description': 'Configured public API host'},
    ],
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        # Keep the UI clean for production use.
        'displayOperationId': False,
        'displayRequestDuration': True,
        'filter': True,
        'tryItOutEnabled': True,
        'docExpansion': 'none',
        'defaultModelsExpandDepth': -1,
        'defaultModelExpandDepth': 2,
        'operationsSorter': 'alpha',
        'tagsSorter': 'alpha',
        # Static asset served by Django staticfiles.
        'customCssUrl': '/static/swagger-ui/tasknepal.css',
    },
    'REDOC_UI_SETTINGS': {
        'hideDownloadButton': False,
        'expandResponses': '200,201',
        'pathInMiddlePanel': True,
    },
    'APPEND_COMPONENTS': {
        'securitySchemes': {
            'BearerAuth': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
                'description': (
                    'JWT access token from `POST /api/v1/auth/login/` or '
                    '`POST /api/v1/auth/token/`. Prefix: `Bearer <token>`.'
                ),
            },
        },
    },
    'SECURITY': [{'BearerAuth': []}],
    'PREPROCESSING_HOOKS': [
        'config.openapi_hooks.preprocess_exclude_admin',
    ],
}

# Security Settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Nepal marketplace — single currency for wallets, tasks, bids, and payments
DEFAULT_CURRENCY = 'NPR'
DEFAULT_CURRENCY_LABEL = 'Nepalese Rupee'

# Escrow: auto-release funds to tasker after completion submitted (hours)
ESCROW_AUTO_RELEASE_HOURS = 48

# Application Settings
TASK_EXPIRY_DAYS = 30
MAX_BIDS_PER_TASK = 50
MIN_TASK_BUDGET = 10
MAX_TASK_BUDGET = 10000
PLATFORM_FEE_PERCENTAGE = 15

# Frontend URL
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:3000')
BACKEND_URL = config('BACKEND_URL', default='http://localhost:8000')

# Social OAuth (Google / Facebook)
GOOGLE_CLIENT_ID = config('GOOGLE_CLIENT_ID', default='')
GOOGLE_CLIENT_SECRET = config('GOOGLE_CLIENT_SECRET', default='')
FACEBOOK_APP_ID = config('FACEBOOK_APP_ID', default='')
FACEBOOK_APP_SECRET = config('FACEBOOK_APP_SECRET', default='')

# Manual wallet recharge — admin WhatsApp (digits only, with country code e.g. 97798XXXXXXXX)
RECHARGE_WHATSAPP_NUMBER = config('RECHARGE_WHATSAPP_NUMBER', default='')

# SMS Gateway Configuration (Nepal)
# Popular options: Sparrow SMS, Aakash SMS, SMS Nepal
SMS_GATEWAY_URL = config('SMS_GATEWAY_URL', default='')
SMS_GATEWAY_TOKEN = config('SMS_GATEWAY_TOKEN', default='')

# Grappelli Admin Theme Configuration
GRAPPELLI_ADMIN_TITLE = "tasknepal Administration"
# Jazzmin Admin Theme Configuration
JAZZMIN_SETTINGS = {
    # Site branding
    "site_title": "tasknepal Admin",
    "site_header": "tasknepal Administration",
    "site_brand": "tasknepal",
    "site_logo": None,
    "site_logo_classes": "img-circle",
    "site_icon": None,
    "welcome_sign": "Welcome to tasknepal Admin Panel",
    "copyright": "tasknepal © 2024",
    
    # Search model in admin
    "search_model": ["users.User", "tasks.Task", "bids.Bid"],
    
    # User menu
    "user_avatar": None,
    
    # Top menu
    "topmenu_links": [
        {"name": "Home", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "API Docs", "url": "/api/docs/", "new_window": True},
        {"name": "Support", "url": "https://github.com/yourusername/airtasker", "new_window": True},
        {"model": "users.User"},
        {"app": "tasks"},
        {"name": "Rules", "app": "rules"},
    ],
    
    # Side menu ordering
    "order_with_respect_to": [
        "dashboard",
        "users",
        "tasks",
        "bids",
        "reviews",
        "chat",
        "notifications",
        "payments",
        "fees",
        "rules",
        "disputes",
        "wallets",
        "search",
        "locations",
        "uploads",
        "blog",
        "accounts",
    ],
    
    # Custom icons for apps and models
    "icons": {
        # Apps
        "dashboard": "fas fa-chart-line",
        "users": "fas fa-users",
        "tasks": "fas fa-tasks",
        "bids": "fas fa-gavel",
        "reviews": "fas fa-star",
        "chat": "fas fa-comments",
        "notifications": "fas fa-bell",
        "payments": "fas fa-credit-card",
        "fees": "fas fa-percentage",
        "rules": "fas fa-gavel",
        "disputes": "fas fa-balance-scale",
        "wallets": "fas fa-wallet",
        "search": "fas fa-search",
        "locations": "fas fa-map-marked-alt",
        "accounts": "fas fa-user-shield",
        "blog": "fas fa-newspaper",
        "analytics": "fas fa-chart-pie",
        "analytics.Event": "fas fa-bolt",
        "analytics.Metric": "fas fa-chart-bar",
        "blog.BlogPost": "fas fa-pen-nib",
        "auth": "fas fa-users-cog",
        
        # Users app models
        "users.User": "fas fa-user",
        "users.UserSkill": "fas fa-tools",
        "users.UserBadge": "fas fa-award",
        "users.UserDocument": "fas fa-file-alt",
        
        # Tasks app models
        "tasks.Category": "fas fa-folder",
        "tasks.Task": "fas fa-clipboard-list",
        "tasks.TaskAttachment": "fas fa-paperclip",
        "tasks.TaskBookmark": "fas fa-bookmark",
        "tasks.TaskView": "fas fa-eye",
        "tasks.TaskQuestion": "fas fa-question-circle",
        "tasks.TaskReport": "fas fa-flag",
        
        # Bids app models
        "bids.Bid": "fas fa-hand-holding-usd",
        "bids.BidMessage": "fas fa-envelope",
        "bids.BidReview": "fas fa-star-half-alt",
        "bids.BidNotification": "fas fa-bell",
        
        # Reviews app models
        "reviews.Review": "fas fa-star",
        "reviews.ReviewPlatformSettings": "fas fa-cog",
        "reviews.ReviewHelpful": "fas fa-thumbs-up",
        "reviews.ReviewReport": "fas fa-exclamation-triangle",
        "reviews.ReviewInvitation": "fas fa-envelope-open-text",
        
        # Chat app models
        "chat.Conversation": "fas fa-comments",
        "chat.Message": "fas fa-comment",
        "chat.TypingIndicator": "fas fa-keyboard",
        "chat.MessageReaction": "fas fa-smile",
        "chat.ConversationMute": "fas fa-volume-mute",
        "chat.MessageReport": "fas fa-flag",
        
        # Notifications app models
        "notifications.Notification": "fas fa-bell",
        "notifications.NotificationPreference": "fas fa-cog",
        "notifications.EmailNotification": "fas fa-envelope",
        "notifications.PushNotification": "fas fa-mobile-alt",
        "notifications.DeviceToken": "fas fa-tablet-alt",
        "notifications.NotificationTemplate": "fas fa-file-code",
        "notifications.NotificationBatch": "fas fa-layer-group",
        
        # Payments app models
        "payments.Payment": "fas fa-money-bill-wave",
        "payments.PlatformFeeSettings": "fas fa-percentage",
        "fees.FeeRule": "fas fa-percentage",
        "fees.FeeTransaction": "fas fa-receipt",
        "rules.RulePolicy": "fas fa-shield-alt",
        "rules.RuleEvaluationLog": "fas fa-clipboard-check",
        "rules.PlatformRule": "fas fa-user-clock",
        "rules.AccountSuspensionLog": "fas fa-user-slash",
        "disputes.Dispute": "fas fa-balance-scale",
        "payments.PaymentMethod": "fas fa-credit-card",
        "payments.Refund": "fas fa-undo",
        "payments.Payout": "fas fa-hand-holding-usd",
        "payments.Transaction": "fas fa-exchange-alt",
        
        # Wallets app models
        "wallets.Wallet": "fas fa-wallet",
        "wallets.WalletTransaction": "fas fa-receipt",
        "wallets.WithdrawalRequest": "fas fa-money-check-alt",
        "wallets.WalletFreeze": "fas fa-lock",
        "wallets.WalletLimit": "fas fa-chart-line",
        
        # Search app models
        "search.SearchHistory": "fas fa-history",
        "search.SavedSearch": "fas fa-bookmark",
        "search.PopularSearch": "fas fa-fire",
        "search.SearchSuggestion": "fas fa-lightbulb",
        "search.SearchFilter": "fas fa-filter",
        
        # Locations app models
        "locations.Country": "fas fa-globe",
        "locations.State": "fas fa-map",
        "locations.City": "fas fa-city",
        "locations.UserLocation": "fas fa-map-pin",
        "locations.ServiceArea": "fas fa-map-marked",
        "locations.LocationSearch": "fas fa-search-location",
        
        # Uploads app models
        "uploads": "fas fa-cloud-upload-alt",
        "uploads.Upload": "fas fa-file-upload",
        "uploads.ImageUpload": "fas fa-image",
        "uploads.DocumentUpload": "fas fa-file-alt",
        "uploads.UploadQuota": "fas fa-database",
        
        # Auth models
        "auth.Group": "fas fa-users",
    },
    
    # Default icon for models without custom icon
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    
    # Related modal
    "related_modal_active": False,
    
    # Custom links to append to app groups
    "custom_links": {
        "dashboard": [{
            "name": "Admin Dashboard",
            "url": "/api/v1/dashboard/admin_dashboard/",
            "icon": "fas fa-tachometer-alt",
            "permissions": ["users.view_user"]
        }],
        "analytics": [{
            "name": "Business analytics",
            "url": "/admin/analytics/",
            "icon": "fas fa-chart-line",
            "permissions": ["users.view_user"]
        }],
        "users": [{
            "name": "User Statistics",
            "url": "/admin/users/user/stats/",
            "icon": "fas fa-chart-bar",
            "permissions": ["users.view_user"]
        }],
        "tasks": [{
            "name": "Task Analytics",
            "url": "/admin/tasks/task/analytics/",
            "icon": "fas fa-chart-line",
            "permissions": ["tasks.view_task"]
        }],
        "payments": [{
            "name": "Payment Reports",
            "url": "/admin/payments/payment/reports/",
            "icon": "fas fa-file-invoice-dollar",
            "permissions": ["payments.view_payment"]
        }],
        "rules": [{
            "name": "Rule policies",
            "url": "/admin/rules/rulepolicy/",
            "icon": "fas fa-shield-alt",
            "permissions": ["rules.view_rulepolicy"]
        }],
    },
    
    # Show/hide apps and models
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    
    # Change view
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "users.user": "collapsible",
        "tasks.task": "horizontal_tabs",
    },
}

# Jazzmin UI Tweaks
JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-primary",
    "accent": "accent-primary",
    "navbar": "navbar-white navbar-light",
    "no_navbar_border": False,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "default",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    },
    "actions_sticky_top": False
}
