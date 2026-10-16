from datetime import timedelta
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from control_plane.apps.fleet.models import BlanketAccessGroup, Host
from control_plane.apps.access_requests.models import (
    AccessRequest,
    AccessRequestState,
    HostAccessAssignment,
)

User = get_user_model()


@receiver(m2m_changed, sender=User.groups.through)
def handle_user_group_membership_changed(sender, instance, action, pk_set, **kwargs):
    """
    Handles automatic provision / revocation when a user is added to or removed from a group.
    """
    if action not in ("post_add", "post_remove") or not pk_set:
        return

    if isinstance(instance, User):
        user = instance
        groups = Group.objects.filter(pk__in=pk_set)
        _sync_user_blanket_access(user, groups, action)
    else:
        group = instance
        users = User.objects.filter(pk__in=pk_set)
        for u in users:
            _sync_user_blanket_access(u, [group], action)


def _sync_user_blanket_access(user, groups, action: str):
    now = timezone.now()
    active_key = user.ssh_public_keys.filter(is_active=True).first() if hasattr(user, "ssh_public_keys") else None
    key_fingerprint = active_key.fingerprint if active_key else "BLANKET_GROUP_KEY"

    for group in groups:
        try:
            blanket = group.blanket_access
        except BlanketAccessGroup.DoesNotExist:
            continue

        target_hosts = (
            list(Host.objects.all())
            if blanket.blanket_all_hosts
            else list(blanket.hosts.all())
        )

        if action == "post_add":
            for host in target_hosts:
                req = AccessRequest.objects.create(
                    requester=user,
                    key_fingerprint=key_fingerprint,
                    access_level=blanket.access_level,
                    is_long_term=True,
                    start_datetime=now,
                    end_datetime=now + timedelta(days=3650),
                    motivation=f"Blanket access via group '{group.name}'",
                    state=AccessRequestState.ACTIVE,
                )
                HostAccessAssignment.objects.get_or_create(access_request=req, host=host)

        elif action == "post_remove":
            blanket_reqs = AccessRequest.objects.filter(
                requester=user,
                motivation__contains=f"Blanket access via group '{group.name}'",
                state=AccessRequestState.ACTIVE,
            )
            for req in blanket_reqs:
                req.state = AccessRequestState.EXPIRED_LOCKED
                req.save()
