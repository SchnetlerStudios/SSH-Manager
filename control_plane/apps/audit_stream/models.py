from django.db import models
from django.core.exceptions import PermissionDenied


class HostAuditEvent(models.Model):
    """
    Append-only compliance audit event log received from host agents.
    ORMs modifications (UPDATE or DELETE) raise PermissionDenied.
    """
    host_identifier = models.CharField(max_length=255, db_index=True)
    event_type = models.CharField(max_length=128)
    auid = models.IntegerField(db_index=True)
    uid = models.IntegerField(null=True, blank=True)
    euid = models.IntegerField(null=True, blank=True)
    pid = models.IntegerField(null=True, blank=True)
    exe = models.CharField(max_length=512, blank=True, default="")
    comm = models.CharField(max_length=255, blank=True, default="")
    command = models.TextField(blank=True, default="")
    raw_line = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise PermissionDenied("HostAuditEvent records are immutable and cannot be updated.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("HostAuditEvent records are immutable and cannot be deleted.")

    def __str__(self) -> str:
        return f"[{self.host_identifier}] auid={self.auid} {self.event_type} {self.exe}"
