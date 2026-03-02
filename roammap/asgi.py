"""
ASGI config for roammap project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""

import os
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.routing import ProtocolTypeRouter, URLRouter
from django.contrib.auth.models import AnonymousUser
from django.core.asgi import get_asgi_application
from rest_framework_simplejwt.authentication import JWTAuthentication

from roammap.routing import websocket_urlpatterns

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "roammap.settings")

django_asgi_app = get_asgi_application()


class JWTAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        scope["user"] = await self._resolve_user(scope)
        return await self.inner(scope, receive, send)

    async def _resolve_user(self, scope):
        token = self._extract_token(scope)
        if not token:
            return AnonymousUser()

        return await self._get_user(token)

    def _extract_token(self, scope):
        query_string = scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)
        query_token = query_params.get("token", [None])[0]
        if query_token:
            return query_token

        for header_name, header_value in scope.get("headers", []):
            if header_name == b"authorization":
                value = header_value.decode("utf-8")
                if value.lower().startswith("bearer "):
                    return value.split(" ", 1)[1].strip()
        return None

    @database_sync_to_async
    def _get_user(self, token):
        try:
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token)
            return jwt_auth.get_user(validated_token)
        except Exception:
            return AnonymousUser()


application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": JWTAuthMiddleware(URLRouter(websocket_urlpatterns)),
    }
)
