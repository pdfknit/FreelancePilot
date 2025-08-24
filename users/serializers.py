from rest_framework import serializers
from .models import UserProfile


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            "id", "hourly_rate", "currency",
            "profession", "seniority", "experience_years",
            "country", "timezone", "tg_id",
        ]
        extra_kwargs = {"tg_id": {"read_only": True}, "id": {"read_only": True}}
