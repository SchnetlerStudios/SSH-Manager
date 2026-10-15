from django.apps import AppConfig

class AuditStreamConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "control_plane.apps.audit_stream"
