from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django_countries.fields import CountryField

class UserProfile(models.Model):
    CURRENCIES = [('EUR', 'EUR'), ('USD', 'USD'), ('RUB', 'RUB')]
    SENIORITY = [('junior', 'Junior'), ('middle', 'Middle'), ('senior', 'Senior'), ('lead', 'Lead')]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    tg_id = models.BigIntegerField(null=True, blank=True, unique=True)
    telegram_username = models.CharField(max_length=32, null=True, blank=True, unique=False, db_index=True, help_text="Ваш Telegram username (без @). Пример: johndoe")
    tg_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, choices=CURRENCIES, default='EUR')
    profession = models.CharField(max_length=100, blank=True, null=True)  # разработчик, дизайнер, тестировщик
    seniority = models.CharField(max_length=10, choices=SENIORITY, blank=True, null=True)
    experience_years = models.PositiveIntegerField(default=0)  # лет опыта
    country = CountryField(blank=True, null=True)


    def __str__(self):
        return f"{self.user} profile"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def _ensure_profile_on_user_create(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
