# tasks/api_views.py
from __future__ import annotations

from datetime import timedelta

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
            rate = getattr(getattr(self.request.user, "profile", None), "hourly_rate", None) or settings.DEFAULT_RATE
            est = estimate(task.raw_text or task.title, hourly_rate=float(rate), confidence="M")
            task.summary = est.summary
            task.est_hours_min = est.est_hours_min
            task.est_hours_max = est.est_hours_max
            task.est_confidence = est.confidence
            task.est_cost = est.est_cost
            task.save()


class TaskEstimateApi(views.APIView):
    def post(self, request, pk: int):
        try:
            task = Task.objects.get(pk=pk)
        except Task.DoesNotExist:
            return Response({"detail": "Task not found"}, status=404)

        rate = getattr(getattr(request.user, "profile", None), "hourly_rate", None) or 25
        confidence = request.data.get("confidence", "M")
        if confidence not in ("L", "M", "H"):
            return Response({"error": "confidence must be one of L, M, H"}, status=400)
        est = estimate(task.raw_text or task.title, hourly_rate=float(rate), confidence=confidence)
        task.summary = est.summary
        task.est_hours_min = est.est_hours_min
        task.est_hours_max = est.est_hours_max
        task.est_confidence = est.confidence
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
    active = TimeEntry.objects.filter(user=request.user, stopped_at__isnull=True).first()
    if active:
        return Response(
            {"error": "You already have an active timer", "entry_id": active.id},
            status=409
        )

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
        return Response({"detail": "No active timer"}, status=409)
    entry.stop(timezone.now())
    return Response(TimeEntrySerializer(entry).data, status=200)


class ReportSummaryApi(APIView):
    def get(self, request):
        qs = TimeEntry.objects.all()

        # фильтр по проекту
        project_id = request.query_params.get("project")
        if project_id:
            qs = qs.filter(task__project_id=project_id)

        # входные даты
        from_str = request.query_params.get("from")
        to_str = request.query_params.get("to")

        # парсер ISO-даты YYYY-MM-DD
        def parse_iso(d: str):
            try:
                return date.fromisoformat(d)
            except Exception:
                return None

        today = timezone.localdate()
        start = parse_iso(from_str)
        end = parse_iso(to_str)

        if start and not end:
            # есть from, нет to → неделя от from (пн-вс относительно from)
            start = start - timedelta(days=start.weekday())
            end = start + timedelta(days=6)
        elif not start and end:
            # есть to, нет from → неделя, заканчивающаяся на to (пн-вс)
            end = end + timedelta(days=(6 - end.weekday()))
            start = end - timedelta(days=6)
        elif not start and not end:
            # оба не заданы → текущая неделя (пн-вс)
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=6)

        # фильтры по дате
        qs = qs.filter(started_at__date__gte=start, started_at__date__lte=end)

        # агрегаты
        total_sec = qs.aggregate(s=Sum("duration_sec"))["s"] or 0
        hrs = round(total_sec / 3600, 2)
        rate = float(getattr(getattr(request.user, "profile", None), "hourly_rate", 0) or settings.DEFAULT_RATE)
        cost = round(hrs * rate, 2)

        return Response({
            "from": start.isoformat(),
            "to": end.isoformat(),
            "hours": hrs,
            "rate": rate,
            "cost": cost,
        })

