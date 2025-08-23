from rest_framework import serializers
from .models import Task, TimeEntry

class TaskCreateSerializer(serializers.ModelSerializer):
    auto_estimate = serializers.BooleanField(write_only=True, required=False, default=False)
    class Meta:
        model = Task
        fields = ["id", "project", "title", "raw_text", "auto_estimate"]

class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ["id","project","title","raw_text","summary","est_hours_min","est_hours_max","est_confidence","est_cost","status","created_at"]

class TimeEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeEntry
        fields = ["id","task","user","started_at","stopped_at","duration_sec"]
        read_only_fields = ["user","duration_sec","stopped_at"]
