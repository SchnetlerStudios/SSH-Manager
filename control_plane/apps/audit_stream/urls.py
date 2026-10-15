from django.urls import path
from control_plane.apps.audit_stream.views import ingest_audit_events_view, compliance_audit_log_view

urlpatterns = [
    path("ingest/", ingest_audit_events_view, name="ingest_audit_events"),
    path("dashboard/", compliance_audit_log_view, name="compliance_audit_log"),
]
