from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

class ChatPage(LoginRequiredMixin, TemplateView):
    template_name = "chat/chat.html"
