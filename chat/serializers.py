from rest_framework import serializers
from .models import MessageLog


class MessageLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageLog
        fields = ['id', 'role', 'text', 'channel', 'created_at']
