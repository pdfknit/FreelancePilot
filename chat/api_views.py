# если файла нет — создай
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

class ChatMessageApi(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        text = (request.data or {}).get("message", "").strip()
        if not text:
            return Response({"reply": "Пустое сообщение 🤷‍♀️"})
        # пока просто эхо-ответ
        return Response({"reply": f"Принято: {text}"})
