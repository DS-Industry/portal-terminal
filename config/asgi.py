"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django_application  = get_asgi_application()

# Импорт routing должен быть после установки настроек
try:
    from orders import routing

    # Настройка WebSocket routing
    websocket_application = AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                routing.websocket_urlpatterns
            )
        )
    )

    # Комбинированное приложение для HTTP и WebSocket
    application = ProtocolTypeRouter({
        "http": django_application,  # Обычные HTTP запросы
        "websocket": websocket_application,  # WebSocket соединения
    })

except ImportError:
    # Если routing еще не настроен, используем только HTTP
    application = django_application
