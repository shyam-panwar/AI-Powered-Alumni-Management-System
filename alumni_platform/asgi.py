"""
ASGI config for alumni_platform project.
"""
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alumni_platform.settings.dev')

django_asgi_app = get_asgi_application()

# Import after Django setup to avoid AppRegistryNotReady
from apps.notifications.routing import websocket_urlpatterns
from apps.notifications.middleware import JWTWebSocketMiddleware

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AllowedHostsOriginValidator(
        JWTWebSocketMiddleware(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
