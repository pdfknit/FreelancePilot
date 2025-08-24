from django import forms
from django_countries.widgets import CountrySelectWidget

from .models import UserProfile


class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            "hourly_rate", "currency",
            "profession", "seniority", "experience_years",
            "country"
        ]
        widgets = {
            "hourly_rate": forms.NumberInput(attrs={"class": "input", "step": "1", "min": "0"}),
            "currency": forms.Select(attrs={"class": "input input-currency"}),
            "profession": forms.TextInput(attrs={"class": "input", "placeholder": "например: dev_backend"}),
            "seniority": forms.Select(attrs={"class": "input"}),
            "experience_years": forms.NumberInput(attrs={"class": "input", "min": "0", "step": "1"}),
            "country": CountrySelectWidget(attrs={"class": "input"}),

        }
        labels = {
            "hourly_rate": "Ставка",
            "currency": "Валюта интерфейса",
            "profession": "Профессия",
            "seniority": "Уровень (seniority)",
            "experience_years": "Опыт, лет",
            "country": "Страна",

        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["hourly_rate"].label = "Ставка"
        self.fields["currency"].label = ""


