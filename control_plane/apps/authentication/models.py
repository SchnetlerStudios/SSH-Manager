import re
from django.db import models
from django.contrib.auth.models import AbstractUser


class CustomUser(AbstractUser):
    entra_oid = models.CharField(max_length=255, unique=True, null=True, blank=True)
    upn = models.EmailField(unique=True, null=True, blank=True)
    posix_username = models.CharField(max_length=32, unique=True, null=True, blank=True)

    def __str__(self) -> str:
        return self.username or self.upn or str(self.id)
