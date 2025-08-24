from django.urls import path
from .api_views import ProfileApi

urlpatterns = [path("profile/", ProfileApi.as_view(), name="api-profile")]
