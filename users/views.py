from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.shortcuts import redirect
from .forms import RateForm

class SettingsView(LoginRequiredMixin, TemplateView):
    template_name = "users/settings.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        u = self.request.user
        ctx["form"] = RateForm(initial={
            "hourly_rate": getattr(u, "hourly_rate", 25),
            "currency": getattr(u, "currency", "USD"),
        })
        ctx["saved"] = self.request.GET.get("saved") == "1"
        return ctx

    def post(self, request, *args, **kwargs):
        form = RateForm(request.POST)
        if form.is_valid():
            u = request.user
            # ⚠️ у стандартного User пока нет полей hourly_rate/currency
            # позже мы сделаем Profile-модель. Сейчас просто имитируем.
            setattr(u, "hourly_rate", form.cleaned_data["hourly_rate"])
            setattr(u, "currency", form.cleaned_data["currency"])
            # u.save() вызовет ошибку, т.к. этих полей нет в базе,
            # поэтому пока пропускаем сохранение.
            return redirect("/settings/?saved=1")
        return self.render_to_response(self.get_context_data(form=form))
