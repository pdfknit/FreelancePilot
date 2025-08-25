from django.db import models
from django.conf import settings


class MessageLog(models.Model):
    CHANNEL_CHOICES = (('page', 'page'), ('widget', 'widget'), ('tg', 'tg'))
    ROLE_CHOICES = (('user', 'user'), ('assistant', 'assistant'))

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                             on_delete=models.SET_NULL, related_name='messages')
    session_key = models.CharField(max_length=40, db_index=True)  # для анонимов
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default='page', db_index=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)  # user / assistant
    text = models.TextField()
    payload = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['session_key', '-created_at']),
        ]
        ordering = ['created_at']

    def __str__(self):
        who = self.user_id or self.session_key[:6]
        return f"{self.created_at:%H:%M} {self.role}({who}): {self.text[:40]}"
