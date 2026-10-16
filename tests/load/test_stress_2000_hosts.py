"""
Stress test suite verifying SSH-Manager platform scalability across 2,000 connected hosts.
"""

import pytest
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from control_plane.apps.fleet.models import Host
from control_plane.apps.access_requests.models import AccessRequest, HostAccessAssignment
from tests.load.agent_simulator import FleetAgentSimulator

User = get_user_model()


@pytest.mark.django_db
def test_stress_2000_connected_hosts_and_updates():
    """
    Stress test that registers 2,000 host instances in Django, creates access request assignments,
    and runs the FleetAgentSimulator to prove 2,000 active host connections and job status updates.
    """
    num_hosts = 2000
    user = User.objects.create_user(username="stress_test_admin", is_staff=True)

    # 1. Bulk create 2,000 hosts
    hosts_to_create = [
        Host(
            hostname=f"sim-node-{i:04d}",
            ip_or_fqdn=f"10.250.{(i // 254) % 254}.{i % 254 + 1}",
            status="ONLINE",
        )
        for i in range(1, num_hosts + 1)
    ]
    Host.objects.bulk_create(hosts_to_create, batch_size=1000)
    assert Host.objects.count() == num_hosts

    all_hosts = list(Host.objects.all())

    # 2. Generate an active AccessRequest targeting all 2,000 hosts
    now = timezone.now()
    request = AccessRequest.objects.create(
        requester=user,
        key_fingerprint="SHA256:stresskey2000",
        start_datetime=now,
        end_datetime=now + timedelta(hours=2),
        motivation="2000 host stress testing simulation",
        state="APPROVED",
    )

    assignments = [
        HostAccessAssignment(access_request=request, host=h)
        for h in all_hosts
    ]
    HostAccessAssignment.objects.bulk_create(assignments, batch_size=1000)
    assert HostAccessAssignment.objects.count() == num_hosts

    # 3. Simulate job fetching and receipt updates for all 2,000 hosts
    # In-memory job state tracking
    active_jobs = {
        h.hostname: [
            {
                "id": idx + 1000,
                "type": "PROVISION",
                "username": "stress_user",
                "raw_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKey stress@test",
                "access_level": "SUDO",
            }
        ]
        for idx, h in enumerate(all_hosts)
    }
    completed_receipts = {}

    def job_fetch_mock(host_id: str):
        return active_jobs.get(host_id, [])

    def receipt_send_mock(job_id: int, host_id: str, status: str, details: str):
        completed_receipts[host_id] = {"job_id": job_id, "status": status, "details": details}
        return True

    simulator = FleetAgentSimulator(num_hosts=num_hosts, max_workers=50)

    # 4. Execute 2,000 host simulation
    results = simulator.simulate_poll_and_update(
        job_fetch_func=job_fetch_mock,
        receipt_send_func=receipt_send_mock,
        batch_size=200,
    )

    # 5. Verify assertions
    assert results["total_hosts"] == num_hosts
    assert results["jobs_found"] == num_hosts
    assert results["successful_receipts"] == num_hosts
    assert len(completed_receipts) == num_hosts
    assert results["elapsed_seconds"] < 10.0  # Must complete within 10 seconds safely
