from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db.models import Q
from django.conf import settings

from .models import MessageLog
from .serializers import MessageLogSerializer
from .utils import ensure_session_key
from chat.services.estimator import estimate


def _get_rate(user):
    if user and hasattr(user, 'profile') and user.profile.hourly_rate:
        return user.profile.hourly_rate
    return getattr(settings, 'DEFAULT_RATE', 25)


class ChatHistoryApi(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        sess = ensure_session_key(request)
        u = request.user if request.user.is_authenticated else None
        qs = MessageLog.objects.filter(Q(user=u) | Q(session_key=sess)).order_by('created_at')[:200]
        return Response({"messages": MessageLogSerializer(qs, many=True).data})


class ChatMessageApi(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        sess = ensure_session_key(request)
        u = request.user if request.user.is_authenticated else None
        text = (request.data.get('text') or '').strip()
        channel = request.data.get('channel') or 'page'
        if not text:
            return Response({"error": "empty"}, status=400)

        MessageLog.objects.create(user=u, session_key=sess, channel=channel, role='user', text=text)

        low = text.lower()
        reply = None

        # в ChatMessageApi.post, после low = text.lower()
        if low in ('команды', 'help', '/help'):
            reply = (
                "Команды:\n"
                "• add <текст> — оценка задачи\n"
                "• estimate <текст> — оценка (синоним)\n"
                "• rate <число> — ставка, $/ч\n"
                "• start <task_id> — старт таймера\n"
                "• stop — стоп таймера\n"
                "• report week — отчёт за неделю\n"
                "\nПримеры:\n"
                "add лендинг с формой и интеграцией API\n"
                "rate 35\n"
                "start 12\n"
                "stop"
            )

        if low.startswith('rate '):
            try:
                val = float(text.split(' ', 1)[1])
                if u and hasattr(u, 'profile'):
                    u.profile.hourly_rate = val
                    u.profile.save(update_fields=['hourly_rate'])
                    reply = f"Ставка обновлена: {val}/ч"
                else:
                    reply = f"Ставка на сессию: {val}/ч (войдите, чтобы сохранить)"
            except:
                reply = "Не удалось разобрать ставку. Пример: rate 25"

        elif low.startswith('add ') or low.startswith('estimate '):
            raw = text.split(' ', 1)[1]
            est = estimate(raw_text=raw, hourly_rate=_get_rate(u))
            reply = (
                    f"Summary: {est.summary}\n"
                    f"Диапазон: {est.est_hours_min}-{est.est_hours_max} ч (conf: {est.confidence})\n"
                    f"Стоимость: {est.est_cost}\n"
                    f"Декомпозиция: " + "; ".join(est.decomposition) + "\n"
                                                                       f"Риски: " + "; ".join(est.risks)
            )
        elif low.startswith('start'):
            reply = "Старт таймера — используйте POST /api/tasks/time/start с task_id (кнопка скоро появится)."
        elif low.startswith('stop'):
            reply = "Стоп таймера — используйте POST /api/tasks/time/stop."

        if not reply:
            reply = f"Принято: {text}"

        MessageLog.objects.create(user=u, session_key=sess, channel=channel, role='assistant', text=reply)
        return Response({"reply": reply})
