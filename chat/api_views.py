# если файла нет — создай
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.utils import timezone
from django.db.models import Q

from .models import MessageLog
from .serializers import MessageLogSerializer
from .utils import ensure_session_key



# История
class ChatHistoryApi(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        limit = int(request.GET.get('limit', 50))
        sess = ensure_session_key(request)
        if request.user.is_authenticated:
            qs = MessageLog.objects.filter(Q(user=request.user) | Q(session_key=sess)).order_by('-created_at')[:limit]
        else:
            qs = MessageLog.objects.filter(session_key=sess).order_by('-created_at')[:limit]
        data = MessageLogSerializer(qs[::-1], many=True).data
        return Response({"messages": data})

class ChatMessageApi(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        text = (request.data or {}).get("message", "").strip()
        channel = (request.data or {}).get("channel", "page")
        if not text:
            return Response({"reply": "Пустое сообщение 🤷‍♀️"})
        sess = ensure_session_key(request)
        u = request.user if request.user.is_authenticated else None

        # 1) пишем сообщение пользователя
        MessageLog.objects.create(
            user=u, session_key=sess, channel=channel, role='user', text=text
        )

        # 2) тут вызываем твой Estimator (пока простой ответ)
        reply = f"Принято: {text}"

        # 3) пишем ответ ассистента
        MessageLog.objects.create(
            user=u, session_key=sess, channel=channel, role='assistant', text=reply
        )

        return Response({"reply": reply})
