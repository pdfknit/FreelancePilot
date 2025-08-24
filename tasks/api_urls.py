
from django.urls import path
from .api_views import (
    TaskListCreateApi,
    TaskEstimateApi,
    time_start,
    time_stop,
    ReportSummaryApi,
)

urlpatterns = [
    path("", TaskListCreateApi.as_view(), name="api_task_list_create"),
    path("<int:pk>/estimate/", TaskEstimateApi.as_view(), name="api_task_estimate"),
    path("time/start/", time_start, name="api_time_start"),
    path("time/stop/", time_stop, name="api_time_stop"),
    path("reports/summary/", ReportSummaryApi.as_view(), name="api_report_summary"),
]
