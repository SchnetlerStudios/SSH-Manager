from django.db import models
from django.conf import settings


class UserSSHPublicKey(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ssh_public_keys",
    )
    raw_key = models.TextField()
    algorithm = models.CharField(max_length=64)
    bits = models.IntegerField()
    fingerprint = models.CharField(max_length=128, unique=True, db_index=True)
    comment = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.user} - {self.fingerprint}"
