import pytest
import json
from django.contrib.auth import get_user_model
from control_plane.apps.onboarding.models import UserSSHPublicKey

User = get_user_model()


@pytest.mark.django_db
def test_blackbox_public_and_auth_routes(client):
    """
    Black-box test suite verifying HTTP interface contracts and redirects.
    """
    # 1. Unauthenticated request to protected route redirects to login or onboarding
    res = client.get("/access-requests/")
    assert res.status_code in (302, 200)

    # 2. Login page renders
    res_login = client.get("/accounts/login/")
    assert res_login.status_code == 200

    # 3. Create user and onboard key
    user = User.objects.create_user(username="bb_user", password="password123")
    UserSSHPublicKey.objects.create(
        user=user,
        raw_key="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA123 bbuser",
        algorithm="ssh-ed25519",
        bits=256,
        fingerprint="SHA256:bbuserkey",
        is_active=True,
    )

    client.force_login(user)

    # 4. Access Requests list endpoint returns 200 OK
    res_reqs = client.get("/access-requests/")
    assert res_reqs.status_code == 200

    # 5. Access Visualization matrix returns 200 OK
    res_viz = client.get("/access/visualize/")
    assert res_viz.status_code == 200

    # 6. Disconnected hosts tab returns 200 OK
    res_disc = client.get("/fleet/disconnected/")
    assert res_disc.status_code == 200

    # 7. Audit Ingest API accepts structured event JSON payload
    payload = {
        "host": "blackbox-host-1",
        "events": [
            {
                "event_type": "USER_START",
                "auid": 1005,
                "command": "/bin/bash",
                "raw_line": "type=USER_START auid=1005",
            }
        ],
    }
    res_audit = client.post(
        "/audit/ingest/", data=json.dumps(payload), content_type="application/json"
    )
    assert res_audit.status_code == 201
