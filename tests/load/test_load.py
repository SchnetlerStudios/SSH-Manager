import pytest
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from control_plane.apps.fleet.models import Host
from control_plane.apps.access_requests.models import AccessRequest, HostAccessAssignment

User = get_user_model()


@pytest.mark.django_db
def test_concurrent_access_requests_load():
    """
    Simulates high-volume access request creation and host assignment load.
    """
    user = User.objects.create_user(username="load_user")
    hosts = [Host.objects.create(hostname=f"load-node-{i}", ip_or_fqdn=f"10.0.0.{i}") for i in range(1, 10)]

    now = timezone.now()
    created_requests = []
    for req_idx in range(50):
        req = AccessRequest.objects.create(
            requester=user,
            key_fingerprint=f"SHA256:loadkey{req_idx}",
            start_datetime=now,
            end_datetime=now + timedelta(hours=1),
            motivation=f"Load test request #{req_idx}",
        )
        for h in hosts[:3]:
            HostAccessAssignment.objects.create(access_request=req, host=h)
        created_requests.append(req)

    assert len(created_requests) == 50
    assert AccessRequest.objects.filter(requester=user).count() == 50
    assert HostAccessAssignment.objects.count() == 150
