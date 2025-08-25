# chat/auth/tg_auth.py

from rest_framework.authentication import BaseAuthentication
from users.models import UserProfile
from django.contrib.auth import get_user_model


class TgIdAuthentication(BaseAuthentication):
    """
    Аутентифицирует запросы по заголовку X-Telegram-ID.
    Находит users.UserProfile.tg_id и возвращает связанного user.
    """

    def authenticate(self, request):
        tg_id = request.headers.get("X-Telegram-ID") or request.headers.get("X-Telegram-Id")
        tg_username = request.headers.get("X-Telegram-Username")

        if tg_id:
            try:
                tg_id_int = int(tg_id)
            except ValueError:
                tg_id_int = None
            if tg_id_int is not None:
                try:
                    profile = UserProfile.objects.select_related("user").get(tg_id=tg_id_int)
                    if profile.user and profile.user.is_active:
                        return profile.user, None
                except UserProfile.DoesNotExist:
                    pass

        # 2) fallback: по username (если админ/пользователь заранее записали его в профиль)
        if tg_username:
            # нормализуем к нижнему регистру
            uname = tg_username.strip().lstrip("@").lower()
            # сначала ищем в profile.telegram_username
            profile = UserProfile.objects.select_related("user").filter(telegram_username__iexact=uname).first()
            if profile and profile.user and profile.user.is_active:
                return profile.user, None

            User = get_user_model()
            user = User.objects.filter(username__iexact=uname, is_active=True).first()
            if user:
                return user, None

        return None
