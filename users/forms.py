import re

from django import forms
from django_countries.widgets import CountrySelectWidget
from django.core.exceptions import ValidationError

from .models import UserProfile

USERNAME_RE = re.compile(r"^[a-z0-9_]{5,32}$")


class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            "hourly_rate", "currency",
            "profession", "seniority", "experience_years",
            "country", "telegram_username",
        ]
        widgets = {
            "hourly_rate": forms.NumberInput(attrs={"class": "input", "step": "1", "min": "0"}),
            "currency": forms.Select(attrs={"class": "input input-currency"}),
            "profession": forms.TextInput(attrs={"class": "input", "placeholder": "например: dev_backend"}),
            "seniority": forms.Select(attrs={"class": "input"}),
            "experience_years": forms.NumberInput(attrs={"class": "input", "min": "0", "step": "1"}),
            "country": CountrySelectWidget(attrs={"class": "input"}),
            "telegram_username": forms.TextInput(attrs={"placeholder": "username (без @)", "autocomplete": "off"}),
        }

        labels = {
            "hourly_rate": "Ставка",
            "currency": "Валюта интерфейса",
            "profession": "Профессия",
            "seniority": "Уровень (seniority)",
            "experience_years": "Опыт, лет",
            "country": "Страна",
            "telegram_username": "Имя пользователя Telegram"
        }

        help_texts = {
            "telegram_username": "5–32 символов: латиница, цифры, подчёркивание. Без @.",
        }

    def clean_telegram_username(self):
        v = (self.cleaned_data.get("telegram_username") or "").strip()
        if not v:
            return None
        v = v.lstrip("@").lower()
        if not USERNAME_RE.match(v):
            raise ValidationError("Допустимы 5–32 символов: латиница, цифры, подчёркивание (без @).")
        return v

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["hourly_rate"].label = "Ставка"
        self.fields["currency"].label = ""
