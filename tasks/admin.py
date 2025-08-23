from django.contrib import admin
from .models import Client, Project, Task, TimeEntry


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "project", "status", "est_hours_min", "est_hours_max", "est_cost", "created_at")
    list_filter = ("status", "project")
    search_fields = ("title", "raw_text", "summary")


admin.site.register(Client)
admin.site.register(Project)
admin.site.register(TimeEntry)
