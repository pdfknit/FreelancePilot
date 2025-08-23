from django.urls import path
from .views import ChatPage

urlpatterns = [ path('', ChatPage.as_view(), name='chat_page') ]
