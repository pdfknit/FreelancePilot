from __future__ import annotations
from django.db import models
from django.conf import settings
from django.utils import timezone


class Client(models.Model):
    name = models.CharField(max_length=200)
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return self.name


class Project(models.Model):
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name="projects")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self): return self.title


class Task(models.Model):
    STATUS = [
        ('open', 'Открыта'),
        ('in_progress', 'В работе'),
        ('paused', 'Пауза'),
        ('done', 'Готово'),
    ]

    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    title = models.CharField(max_length=255)
    raw_text = models.TextField(blank=True, default='')
    summary = models.TextField(blank=True, default='')

    est_hours_min = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    est_hours_max = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    est_confidence = models.CharField(max_length=1, choices=[('L', 'L'), ('M', 'M'), ('H', 'H')], blank=True,
                                      default='')
    est_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS, default='open')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    def __str__(self) -> str:
        return self.title


class TimeEntry(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='time_entries')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='time_entries')
    started_at = models.DateTimeField()
    stopped_at = models.DateTimeField(null=True, blank=True)
    duration_sec = models.PositiveIntegerField(null=True, blank=True)

    def stop(self, stopped_at):
        self.stopped_at = stopped_at
        if self.started_at and self.stopped_at:
            self.duration_sec = max(0, int((self.stopped_at - self.started_at).total_seconds()))
        self.save(update_fields=["stopped_at", "duration_sec"])
        return self

    def __str__(self) -> str:
        return f"{self.user} · {self.task} · {self.duration_sec}s"
