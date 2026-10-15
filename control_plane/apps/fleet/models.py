from django.db import models


class HostGroup(models.Model):
    name = models.CharField(max_length=128, unique=True)
    slug = models.SlugField(max_length=128, unique=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )

    def __str__(self) -> str:
        return self.name


class AccountSetupProfile(models.Model):
    name = models.CharField(max_length=128, unique=True)
    shell = models.CharField(max_length=64, default="/bin/bash")
    supplementary_groups = models.CharField(max_length=255, blank=True, default="")
    ansible_playbook_path = models.CharField(max_length=512, blank=True, default="")

    def __str__(self) -> str:
        return self.name


class Host(models.Model):
    STATUS_CHOICES = [
        ("ONLINE", "Online"),
        ("OFFLINE", "Offline"),
        ("MAINTENANCE", "Maintenance"),
    ]

    hostname = models.CharField(max_length=255, unique=True, db_index=True)
    ip_or_fqdn = models.CharField(max_length=255)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="ONLINE")
    mtls_cert_fingerprint = models.CharField(max_length=128, blank=True, default="")
    os_distribution = models.CharField(max_length=128, blank=True, default="Ubuntu 24.04")
    group = models.ForeignKey(
        HostGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hosts",
    )
    profile = models.ForeignKey(
        AccountSetupProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hosts",
    )
    last_heartbeat = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return self.hostname
