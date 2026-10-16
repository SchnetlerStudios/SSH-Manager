from django.apps import AppConfig

class FleetConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "control_plane.apps.fleet"

    def ready(self):
        import control_plane.apps.fleet.signals  # noqa: F401
