from django.urls import path, include
from .views import SettingsView

urlpatterns = [
    path('', SettingsView.as_view(), name='settings'),
    path('accounts/signup/', include('users.signup_urls')),

]
