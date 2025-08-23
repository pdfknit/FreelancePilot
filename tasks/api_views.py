from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.conf import settings

from .models import Task, TimeEntry
from .serializers import TaskCreateSerializer, TaskSerializer
from chat.services.estimator import estimate


def _get_rate(user):
    if hasattr(user, "profile") and user.profile.hourly_rate:
        return user.profile.hourly_rate
    return getattr(settings, 'DEFAULT_RATE', 25)


class TaskListCreateApi(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Task.objects.all().order_by("-created_at")[:200]
        return Response(TaskSerializer(qs, many=True).data)

    def post(self, request):
        ser = TaskCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = Task.objects.create(
            project=ser.validated_data.get("project"),
            title=ser.validated_data["title"],
            raw_text=ser.validated_data.get("raw_text", ""),
            status="open",
        )
        if ser.validated_data.get("auto_estimate"):
            est = estimate(obj.raw_text, _get_rate(request.user))
            obj.summary = est.summary
            obj.est_hours_min = est.est_hours_min
            obj.est_hours_max = est.est_hours_max
            obj.est_confidence = est.confidence
            obj.est_cost = est.est_cost
            obj.save()
        return Response(TaskSerializer(obj).data, status=201)


class TaskEstimateApi(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        obj = get_object_or_404(Task, pk=pk)
        est = estimate(obj.raw_text or obj.title, _get_rate(request.user))
        obj.summary = est.summary
        obj.est_hours_min = est.est_hours_min
        obj.est_hours_max = est.est_hours_max
        obj.est_confidence = est.confidence
        obj.est_cost = est.est_cost
        obj.save()
        return Response(TaskSerializer(obj).data)


class TimeStartApi(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        task_id = request.data.get("task_id")
        task = get_object_or_404(Task, pk=task_id)
        # закрыть незакрытые
        TimeEntry.objects.filter(user=request.user, stopped_at__isnull=True).update(stopped_at=timezone.now())
        te = TimeEntry.objects.create(task=task, user=request.user, started_at=timezone.now())
        return Response({"ok": True, "time_entry_id": te.id})


class TimeStopApi(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        te = TimeEntry.objects.filter(user=request.user, stopped_at__isnull=True).order_by("-started_at").first()
        if not te:
            return Response({"error": "no running timer"}, status=400)
        te.stop(timezone.now())
        return Response({"ok": True, "time_entry_id": te.id, "duration_sec": te.duration_sec})


class ReportSummaryApi(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # простой отчёт: суммарные секунды и стоимость за период (если не передан — за 30 дней)
        from_dt = request.GET.get("from")
        to_dt = request.GET.get("to")
        qs = TimeEntry.objects.filter(user=request.user, stopped_at__isnull=False)
        # (для MVP не парсим даты подробно; можно расширить позже)
        total_sec = sum(qs.values_list("duration_sec", flat=True) or [0])
        hours = round(total_sec / 3600, 2)
        cost = round(hours * float(_get_rate(request.user)), 2)
        return Response({"hours": hours, "cost": cost})
