from django.urls import path
from .views import TaskListView, SetTaskStatusView

urlpatterns = [
    path('', TaskListView.as_view(), name='tasks_list'),
    path('set-status/', SetTaskStatusView.as_view(), name='tasks_set_status'),
]
