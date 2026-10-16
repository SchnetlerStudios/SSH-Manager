import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from control_plane.apps.fleet.models import Host, BlanketAccessGroup
from control_plane.apps.access_requests.models import AccessRequest, AccessRequestState

User = get_user_model()


@pytest.mark.django_db
def test_blanket_access_group_auto_provision_and_revocation():
    user = User.objects.create_user(username="rig_engineer")
    host1 = Host.objects.create(hostname="rig-m1", ip_or_fqdn="10.0.1.1")
    host2 = Host.objects.create(hostname="rig-m2", ip_or_fqdn="10.0.1.2")

    group = Group.objects.create(name="Rig Engineers")
    blanket = BlanketAccessGroup.objects.create(
        name="Rig Engineers Blanket",
        group=group,
        blanket_all_hosts=True,
        access_level="NORMAL",
    )

    assert str(blanket) == "BlanketAccessGroup: Rig Engineers Blanket"

    # Add user to group -> auto-provisions access to all hosts
    user.groups.add(group)

    active_reqs = AccessRequest.objects.filter(
        requester=user, state=AccessRequestState.ACTIVE
    )
    assert active_reqs.count() == 2

    # Remove user from group -> revokes blanket access
    user.groups.remove(group)

    active_reqs_after = AccessRequest.objects.filter(
        requester=user, state=AccessRequestState.ACTIVE
    )
    assert active_reqs_after.count() == 0

    expired_reqs = AccessRequest.objects.filter(
        requester=user, state=AccessRequestState.EXPIRED_LOCKED
    )
    assert expired_reqs.count() == 2
