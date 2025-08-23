from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.generic import TemplateView
from .models import Task


class TaskListView(LoginRequiredMixin, TemplateView):
    template_name = "tasks/list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["tasks"] = Task.objects.order_by("-created_at")[:200]
        ctx["TASK_STATUSES"] = Task.STATUS
        return ctx


class ReportsView(LoginRequiredMixin, TemplateView):
    template_name = "reports/summary.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # тут можно будет подставить реальные агрегаты из API/модели
        return ctx


class SetTaskStatusView(LoginRequiredMixin, View):
    def post(self, request):
        task_id = request.POST.get("task_id")
        status = (request.POST.get("status") or "").strip()
        if not task_id or not status:
            return HttpResponseBadRequest("missing params")
        task = get_object_or_404(Task, pk=task_id)
        allowed = {k for k, _ in Task.STATUS}
        if status not in allowed:
            return HttpResponseBadRequest("bad status")
        task.status = status
        task.save(update_fields=["status"])
        return JsonResponse({"ok": True, "task_id": task.id, "status": task.status})
