from django.contrib import admin
from django.urls import path, include
from control_plane.apps.access_requests.views_home import home_view

urlpatterns = [
    path("", home_view, name="home"),
    path("admin/", admin.site.urls),
    path("accounts/", include("control_plane.apps.authentication.urls")),
    path("onboarding/", include("control_plane.apps.onboarding.urls")),
    path("access-requests/", include("control_plane.apps.access_requests.urls")),
    path("audit/", include("control_plane.apps.audit_stream.urls")),
]
