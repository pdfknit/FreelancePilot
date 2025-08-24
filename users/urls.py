from django.urls import path, include
from .views import SettingsView, SettingsPageView

urlpatterns = [
    path('', SettingsView.as_view(), name='settings'),
    path('accounts/signup/', include('users.signup_urls')),
    path("settings/", SettingsPageView.as_view(), name="settings")

]
