from django.urls import path
from .api_views import TaskListCreateApi, TaskEstimateApi, TimeStartApi, TimeStopApi, ReportSummaryApi

urlpatterns = [
    path('', TaskListCreateApi.as_view(), name='api_tasks'),
    path('<int:pk>/estimate/', TaskEstimateApi.as_view(), name='api_task_estimate'),
    path('time/start/', TimeStartApi.as_view(), name='api_time_start'),
    path('time/stop/', TimeStopApi.as_view(), name='api_time_stop'),
    path('reports/summary/', ReportSummaryApi.as_view(), name='api_reports_summary'),
]
