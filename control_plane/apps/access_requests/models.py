from django.db import models
from django.conf import settings
from control_plane.apps.fleet.models import Host


class AccessRequestState(models.TextChoices):
    PENDING = "PENDING", "Pending Approval"
    APPROVED = "APPROVED", "Approved"
    DENIED = "DENIED", "Denied"
    ACTIVE = "ACTIVE", "Active Provisioned"
    EXPIRED_LOCKED = "EXPIRED_LOCKED", "Expired & Locked"
    PURGED = "PURGED", "Purged"


class AccessLevel(models.TextChoices):
    NORMAL = "NORMAL", "Normal User"
    SUDO = "SUDO", "Sudo Admin"


class PrivilegeElevationState(models.TextChoices):
    PENDING = "PENDING", "Pending Approval"
    APPROVED = "APPROVED", "Approved"
    DENIED = "DENIED", "Denied"
    ACTIVE = "ACTIVE", "Active Elevated"
    EXPIRED = "EXPIRED", "Expired (Dropped to Normal)"


class AccessRequest(models.Model):
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="access_requests",
    )
    key_fingerprint = models.CharField(max_length=128)
    access_level = models.CharField(
        max_length=16,
        choices=AccessLevel.choices,
        default=AccessLevel.NORMAL,
    )
    is_long_term = models.BooleanField(
        default=False,
        help_text="Long-term access request across all or selected fleet machines",
    )
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    motivation = models.TextField()
    state = models.CharField(
        max_length=32,
        choices=AccessRequestState.choices,
        default=AccessRequestState.PENDING,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_requests",
    )
    review_datetime = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Request #{self.id} - {self.requester} ({self.state})"


class HostAccessAssignment(models.Model):
    access_request = models.ForeignKey(
        AccessRequest,
        on_delete=models.CASCADE,
        related_name="host_assignments",
    )
    host = models.ForeignKey(
        Host,
        on_delete=models.CASCADE,
        related_name="access_assignments",
    )

    class Meta:
        unique_together = ("access_request", "host")

    def __str__(self) -> str:
        return f"{self.access_request} -> {self.host}"


class PrivilegeElevationRequest(models.Model):
    parent_request = models.ForeignKey(
        AccessRequest,
        on_delete=models.CASCADE,
        related_name="elevation_requests",
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="elevation_requests",
    )
    hosts = models.ManyToManyField(Host, related_name="elevation_requests")
    elevation_start_datetime = models.DateTimeField()
    elevation_end_datetime = models.DateTimeField()
    reason = models.TextField()
    state = models.CharField(
        max_length=32,
        choices=PrivilegeElevationState.choices,
        default=PrivilegeElevationState.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Elevation #{self.id} for Request #{self.parent_request_id} ({self.state})"
