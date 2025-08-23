from django.urls import path
from .api_views import ChatMessageApi, ChatHistoryApi

urlpatterns = [
    path("", ChatMessageApi.as_view(), name="api_chat_root"),
    path('message/', ChatMessageApi.as_view(), name='chat_message_api'),
    path('history/', ChatHistoryApi.as_view(), name='chat_history_api'),
]
