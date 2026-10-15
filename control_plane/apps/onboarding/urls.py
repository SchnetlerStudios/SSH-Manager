from django.urls import path
from control_plane.apps.onboarding.views import register_ssh_key_view

urlpatterns = [
    path("ssh-key/", register_ssh_key_view, name="register_ssh_key"),
]
