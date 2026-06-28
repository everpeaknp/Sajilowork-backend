"""
ASGI config for airtasker project.
Supports both HTTP and WebSocket protocols.
"""
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

# Import routing after Django is initialized
from django.conf import settings
from apps.chat.routing import websocket_urlpatterns
from apps.chat.middleware import JwtAuthMiddlewareStack


def _build_websocket_stack():
    """Wrap chat routes with origin checks appropriate for the environment."""
    inner = JwtAuthMiddlewareStack(URLRouter(websocket_urlpatterns))
    if settings.DEBUG:
        # Local dev: browsers connect from localhost:3000; skip strict origin checks.
        return inner
    return AllowedHostsOriginValidator(inner)


# Full WebSocket + HTTP application
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": _build_websocket_stack(),
})
