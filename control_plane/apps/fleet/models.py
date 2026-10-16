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
    pam_audit_enabled = models.BooleanField(
        default=True, help_text="Enable PAM loginuid and command audit tracking"
    )
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


class HookStage(models.TextChoices):
    PRE_CONNECT = "PRE_CONNECT", "Pre-Connect"
    POST_DISCONNECT = "POST_DISCONNECT", "Post-Disconnect"


class AutomationTaskType(models.TextChoices):
    PYTHON_SCRIPT = "PYTHON_SCRIPT", "Python Script"
    SHELL_SCRIPT = "SHELL_SCRIPT", "Shell Script"
    WEBHOOK_JENKINS = "WEBHOOK_JENKINS", "Jenkins Webhook"
    WEBHOOK_AWX = "WEBHOOK_AWX", "AWX Webhook"
    WEBHOOK_MAAS = "WEBHOOK_MAAS", "MAAS Webhook"


class AutomationTask(models.Model):
    name = models.CharField(max_length=255)
    hook_stage = models.CharField(
        max_length=32, choices=HookStage.choices, default=HookStage.PRE_CONNECT
    )
    task_type = models.CharField(
        max_length=32, choices=AutomationTaskType.choices, default=AutomationTaskType.PYTHON_SCRIPT
    )
    content_or_url = models.TextField(
        help_text="Script content, binary path, or webhook URL endpoint"
    )
    estimated_runtime_minutes = models.PositiveIntegerField(
        default=10,
        help_text="Estimated runtime in minutes to offset pre-connect execution start time",
    )
    headers_or_payload = models.JSONField(blank=True, default=dict)
    hosts = models.ManyToManyField(Host, blank=True, related_name="automation_tasks")
    host_groups = models.ManyToManyField(
        HostGroup, blank=True, related_name="automation_tasks"
    )
    is_global = models.BooleanField(
        default=False, help_text="If true, applies to all hosts"
    )

    def __str__(self) -> str:
        return f"{self.name} ({self.hook_stage} - {self.task_type})"


class AutomationTaskExecution(models.Model):
    task = models.ForeignKey(
        AutomationTask, on_delete=models.CASCADE, related_name="executions"
    )
    access_request = models.ForeignKey(
        "access_requests.AccessRequest",
        on_delete=models.CASCADE,
        related_name="automation_executions",
    )
    scheduled_start_time = models.DateTimeField()
    actual_start_time = models.DateTimeField(null=True, blank=True)
    completed_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=32,
        choices=[
            ("SCHEDULED", "Scheduled"),
            ("RUNNING", "Running"),
            ("SUCCESS", "Success"),
            ("FAILED", "Failed"),
        ],
        default="SCHEDULED",
    )
    output_log = models.TextField(blank=True, default="")

    def __str__(self) -> str:
        return f"Execution of {self.task.name} for Request #{self.access_request_id} ({self.status})"


class BlanketAccessGroup(models.Model):
    name = models.CharField(max_length=255, unique=True)
    group = models.OneToOneField(
        "auth.Group", on_delete=models.CASCADE, related_name="blanket_access"
    )
    blanket_all_hosts = models.BooleanField(
        default=True, help_text="Grant blanket access to all machines in fleet"
    )
    hosts = models.ManyToManyField(Host, blank=True, related_name="blanket_groups")
    access_level = models.CharField(
        max_length=16,
        choices=[("NORMAL", "Normal User"), ("SUDO", "Sudo Admin")],
        default="NORMAL",
    )

    def __str__(self) -> str:
        return f"BlanketAccessGroup: {self.name}"
