from django import forms


class RateForm(forms.Form):
    hourly_rate = forms.DecimalField(
        min_value=1,
        max_digits=8,
        decimal_places=2,
        label="Ставка ($/ч)",
        widget=forms.NumberInput(attrs={'class': 'input'})
    )
    currency = forms.ChoiceField(
        choices=[('USD', 'USD'), ('EUR', 'EUR'), ('RUB', 'RUB')],
        label="Валюта",
        widget=forms.Select(attrs={'class': 'input'})
    )
