from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "tg_id", "hourly_rate", "currency")
    search_fields = ("user__username", "tg_id")
