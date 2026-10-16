from django.urls import path
from control_plane.apps.fleet.views import disconnected_hosts_view

urlpatterns = [
    path("disconnected/", disconnected_hosts_view, name="disconnected_hosts"),
]
