from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import TemplateView, FormView
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
            if hasattr(u, "profile"):
                u.profile.hourly_rate = form.cleaned_data["hourly_rate"]
                u.profile.currency = form.cleaned_data["currency"]
                u.profile.save(update_fields=["hourly_rate", "currency"])
            return redirect("/settings/?saved=1")
        return self.render_to_response(self.get_context_data(form=form))


class SignupView(FormView):
    template_name = "registration/signup.html"
    form_class = UserCreationForm
    success_url = reverse_lazy("login")  # после регистрации → на логин

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)
