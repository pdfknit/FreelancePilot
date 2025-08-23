# tasks/api_views.py
from __future__ import annotations

from django.conf import settings
from django.utils import timezone
from django.db.models import Sum
from rest_framework import generics, status, views
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Task, TimeEntry, Project
from .serializers import TaskSerializer, TimeEntrySerializer
from chat.services.estimator import estimate


class TaskListCreateApi(generics.ListCreateAPIView):
    queryset = Task.objects.all().order_by("-created_at")
    serializer_class = TaskSerializer

    def perform_create(self, serializer):
        task = serializer.save()
        auto = self.request.query_params.get("auto_estimate") or self.request.data.get("auto_estimate")
        if str(auto).lower() in {"1", "true", "yes"}:
            rate = getattr(getattr(self.request.user, "userprofile", None), "hourly_rate", None) or 25
            est = estimate(task.raw_text or task.title, hourly_rate=float(rate), confidence="M")
            task.summary = est.summary
            task.est_hours_min = est.est_hours_min
            task.est_hours_max = est.est_hours_max
            # task.est_confidence = est.est_confidence
            task.est_cost = est.est_cost
            task.save()


class TaskEstimateApi(views.APIView):
    def post(self, request, pk: int):
        try:
            task = Task.objects.get(pk=pk)
        except Task.DoesNotExist:
            return Response({"detail": "Task not found"}, status=404)

        rate = getattr(getattr(request.user, "userprofile", None), "hourly_rate", None) or 25
        conf = request.data.get("confidence", "M")
        est = estimate(task.raw_text or task.title, hourly_rate=float(rate), confidence=conf)
        task.summary = est.summary
        task.est_hours_min = est.est_hours_min
        task.est_hours_max = est.est_hours_max
        task.est_confidence = est.est_confidence
        task.est_cost = est.est_cost
        task.save()
        return Response(TaskSerializer(task).data, status=200)


@api_view(["POST"])
def time_start(request):
    task_id = request.data.get("task_id")
    if not task_id:
        return Response({"detail": "task_id required"}, status=400)
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return Response({"detail": "Task not found"}, status=404)
    entry = TimeEntry.objects.create(task=task, user=request.user, started_at=timezone.now())
    return Response(TimeEntrySerializer(entry).data, status=201)


@api_view(["POST"])
def time_stop(request):
    entry = (
        TimeEntry.objects.filter(user=request.user, stopped_at__isnull=True)
        .order_by("-started_at")
        .first()
    )
    if not entry:
        return Response({"detail": "No running entry"}, status=400)
    entry.stop(timezone.now())
    return Response(TimeEntrySerializer(entry).data, status=200)


class ReportSummaryApi(APIView):
    def get(self, request):
        qs = TimeEntry.objects.all()

        # фильтр по проекту
        project_id = request.query_params.get("project")
        if project_id:
            qs = qs.filter(task__project_id=project_id)

        # фильтры по дате
        from_str = request.query_params.get("from")
        to_str = request.query_params.get("to")
        if from_str:
            qs = qs.filter(started_at__date__gte=from_str)
        if to_str:
            qs = qs.filter(started_at__date__lte=to_str)

        # агрегаты
        total_sec = qs.aggregate(s=Sum("duration_sec"))["s"] or 0
        hrs = round(total_sec / 3600, 2)
        rate = float(getattr(getattr(request.user, "userprofile", None), "hourly_rate", 0) or settings.DEFAULT_RATE)
        cost = round(hrs * rate, 2)

        return Response({"hours": hrs, "cost": cost})

