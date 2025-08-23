from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

class TaskListView(LoginRequiredMixin, TemplateView):
    template_name = "tasks/list.html"
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Заглушечные данные, чтобы таблица не была пустой
        ctx['tasks'] = [
            {"id": 1, "title": "Сделать лендинг", "est_hours_min": 6, "est_hours_max": 10, "est_cost": 250, "status": "open"},
            {"id": 2, "title": "Бот для Телеграм", "est_hours_min": 4, "est_hours_max": 7, "est_cost": 180, "status": "done"},
        ]
        return ctx

class ReportsView(LoginRequiredMixin, TemplateView):
    template_name = "reports/summary.html"
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Заглушечные метрики
        ctx['hours'] = 12.5
        ctx['cost'] = 312.5
        return ctx
