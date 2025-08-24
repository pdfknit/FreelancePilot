# tasks/serializers.py
from rest_framework import serializers
from .models import Task, TimeEntry


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            "id",
            "project",
            "title",
            "raw_text",
            "summary",
            "est_hours_min",
            "est_hours_max",  # важно: без лишних символов
            "est_confidence",
            "est_cost",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "summary",
            "est_hours_min",
            "est_hours_max",
            "est_confidence",
            "est_cost",
            "created_at",
            "updated_at",
        ]


class TimeEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeEntry
        fields = [
            "id",
            "project",
            "title",
            "raw_text",
            "summary",
            "est_hours_min",
            "est_hours_max",
            "est_confidence",
            "est_cost",
            "status",
            "created_at",
            "updated_at"
        ]
        read_only_fields = [
            "summary",
            "est_hours_min",
            "est_hours_max",
            "est_confidence",
            "est_cost",
            "created_at",
            "updated_at"
        ]
