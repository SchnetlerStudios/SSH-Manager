from django.urls import path
from control_plane.apps.access_requests.views import (
    list_access_requests_view,
    create_access_request_view,
    review_access_request_view,
)

urlpatterns = [
    path("", list_access_requests_view, name="list_access_requests"),
    path("create/", create_access_request_view, name="create_access_request"),
    path("<int:request_id>/review/", review_access_request_view, name="review_access_request"),
]
