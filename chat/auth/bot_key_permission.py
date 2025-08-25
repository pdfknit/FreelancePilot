# chat/auth/bot_key_permission.py
from rest_framework.permissions import BasePermission
from django.conf import settings


class HasBotApiKey(BasePermission):
    def has_permission(self, request, view):
        required = getattr(settings, "BOT_API_KEY", "")
        if not required:
            return True  # если ключ не настроен — пропускаем
        return request.headers.get("X-API-Key") == required
