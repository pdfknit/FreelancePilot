from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import FormView
from django.shortcuts import redirect
from django.views.generic import TemplateView
from .forms import ProfileForm
from .models import UserProfile


class SettingsView(LoginRequiredMixin, TemplateView):
    template_name = "users/settings.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        ctx["form"] = ProfileForm(instance=profile)
        ctx["saved"] = self.request.GET.get("saved") == "1"
        return ctx

    def post(self, request, *args, **kwargs):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect("/settings/?saved=1")

        ctx = self.get_context_data()
        ctx["form"] = form
        return self.render_to_response(ctx)


class SignupView(FormView):
    template_name = "registration/signup.html"
    form_class = UserCreationForm
    success_url = reverse_lazy("login")  # после регистрации → на логин

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)


class SettingsPageView(LoginRequiredMixin, TemplateView):
    template_name = "users/settings.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        p = self.request.user.profile
        ctx.update({
            "hourly_rate": p.hourly_rate or "",
            "currency": p.currency or "EUR",
            "profession": p.profession or "",
            "seniority": getattr(p, "seniority", "") or "",
            "experience_years": p.experience_years or 0,
            "country": p.country or "",
            "timezone": getattr(p, "timezone", "") or "",
        })
        return ctx
