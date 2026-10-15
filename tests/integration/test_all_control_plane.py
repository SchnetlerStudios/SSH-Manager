import pytest
import json
from datetime import timedelta
from unittest.mock import patch, MagicMock
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from control_plane.apps.authentication.backends import EntraIDOIDCBackend
from control_plane.apps.authentication.models import CustomUser
from control_plane.apps.onboarding.models import UserSSHPublicKey
from control_plane.apps.onboarding.middleware import _has_url
from control_plane.apps.fleet.models import Host, HostGroup, AccountSetupProfile
from control_plane.apps.access_requests.models import (
    AccessRequest,
    AccessRequestState,
    AccessLevel,
    HostAccessAssignment,
)
from control_plane.apps.access_requests.tasks import dispatch_request_notification
from control_plane.apps.audit_stream.models import HostAuditEvent
from tests.unit.test_crypto_utils import generate_ed25519_key_str

User = get_user_model()


@pytest.mark.django_db
def test_onboarding_views_and_middleware(client):
    user = User.objects.create_user(username="onboard_user", password="password")

    # Middleware redirect
    client.force_login(user)
    res = client.get("/access-requests/")
    assert res.status_code == 302
    assert "/onboarding/ssh-key/" in res.url

    # GET onboarding view
    res_get = client.get("/onboarding/ssh-key/")
    assert res_get.status_code == 200

    # POST valid key
    key_str = generate_ed25519_key_str(comment="onboard@test")
    res_post = client.post("/onboarding/ssh-key/", {"raw_key": key_str})
    assert res_post.status_code == 302

    key = UserSSHPublicKey.objects.get(user=user, is_active=True)
    assert str(key) == f"{user} - {key.fingerprint}"

    # POST invalid key
    res_bad = client.post("/onboarding/ssh-key/", {"raw_key": "invalid_single_token"})
    assert res_bad.status_code == 200

    assert not _has_url("invalid_reverse_name_12345")


@pytest.mark.django_db
def test_oidc_auth_backend():
    backend = EntraIDOIDCBackend()

    claims = {
        "oid": "11111111-1111-1111-1111-111111111111",
        "upn": "oidc.user@company.com",
        "roles": ["Access.User"],
    }
    user = backend.authenticate_oidc_claims(claims)
    assert user is not None
    assert str(user) == "oidc.user@company.com"

    # Admin upgrade
    claims["roles"] = ["Access.Admin"]
    admin = backend.authenticate_oidc_claims(claims)
    assert admin.is_staff and admin.is_superuser

    # Demote
    claims["roles"] = []
    user_demoted = backend.authenticate_oidc_claims(claims)
    assert not user_demoted.is_staff

    # Update UPN
    claims["upn"] = "updated.oidc@company.com"
    user_updated = backend.authenticate_oidc_claims(claims)
    assert user_updated.upn == "updated.oidc@company.com"

    # Clear posix_username to cover fallback branch
    user_updated.posix_username = ""
    user_updated.save()
    user_re_auth = backend.authenticate_oidc_claims(claims)
    assert user_re_auth.posix_username == "updated_oidc"

    assert backend.authenticate_oidc_claims({}) is None
    assert backend.authenticate_oidc_claims({"oid": "123"}) is None


@pytest.mark.django_db
def test_fleet_and_access_request_models_and_views(client):
    admin = User.objects.create_superuser(
        username="admin_fleet", password="password", upn="admin@fleet.com"
    )
    UserSSHPublicKey.objects.create(
        user=admin,
        raw_key="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA123 admin",
        algorithm="ssh-ed25519",
        bits=256,
        fingerprint="SHA256:adminfleetkey",
        is_active=True,
    )

    regular_user = User.objects.create_user(username="regular_user", upn="")
    UserSSHPublicKey.objects.create(
        user=regular_user,
        raw_key="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA123 reg",
        algorithm="ssh-ed25519",
        bits=256,
        fingerprint="SHA256:regkey",
        is_active=True,
    )

    parent_grp = HostGroup.objects.create(name="ParentGrp", slug="parent")
    child_grp = HostGroup.objects.create(name="ChildGrp", slug="child", parent=parent_grp)
    profile = AccountSetupProfile.objects.create(name="DevProfile", shell="/bin/bash")
    host = Host.objects.create(
        hostname="fleet-01", ip_or_fqdn="10.0.0.10", group=child_grp, profile=profile
    )

    assert str(parent_grp) == "ParentGrp"
    assert str(profile) == "DevProfile"
    assert str(host) == "fleet-01"

    now = timezone.now()
    req = AccessRequest.objects.create(
        requester=admin,
        key_fingerprint="SHA256:adminfleetkey",
        access_level=AccessLevel.SUDO,
        start_datetime=now - timedelta(minutes=5),
        end_datetime=now + timedelta(hours=2),
        motivation="Fleet test",
        state=AccessRequestState.PENDING,
    )
    assignment = HostAccessAssignment.objects.create(access_request=req, host=host)

    assert str(req) == f"Request #{req.id} - {admin} (PENDING)"
    assert str(assignment) == f"{req} -> {host}"

    client.force_login(admin)

    # List requests view
    res_list = client.get("/access-requests/")
    assert res_list.status_code == 200

    # Review deny
    res_deny = client.post(
        f"/access-requests/{req.id}/review/", {"action": "deny", "rejection_reason": "Denied"}
    )
    assert res_deny.status_code == 302
    req.refresh_from_db()
    assert req.state == AccessRequestState.DENIED

    # Reviewing non-pending request returns redirect
    res_re_deny = client.post(f"/access-requests/{req.id}/review/", {"action": "deny"})
    assert res_re_deny.status_code == 302

    # Create request GET view
    res_create_get = client.get("/access-requests/create/")
    assert res_create_get.status_code == 200
    html_content = res_create_get.content.decode("utf-8")
    assert '<html lang="en">' in html_content
    assert 'for="id_hosts"' in html_content
    assert 'id="id_hosts"' in html_content
    assert 'aria-required="true"' in html_content

    # Create request POST view
    res_create = client.post(
        "/access-requests/create/",
        {
            "hosts": "fleet-[01:01]",
            "access_level": "NORMAL",
            "start_datetime": (now - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M"),
            "end_datetime": (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
            "motivation": "New request",
        },
    )
    assert res_create.status_code == 302

    # Regular user list view
    client.force_login(regular_user)
    res_reg_list = client.get("/access-requests/")
    assert res_reg_list.status_code == 200

    # Regular user post without key redirects
    no_key_user = User.objects.create_user(username="nokeyuser")
    client.force_login(no_key_user)
    res_nokey = client.post("/access-requests/create/", {})
    assert res_nokey.status_code == 302
    assert "/onboarding/ssh-key/" in res_nokey.url


@pytest.mark.django_db
@patch("requests.post")
def test_tasks_notification_and_audit_views(mock_post, client, settings):
    settings.TEAMS_WEBHOOK_URL = "https://outlook.office.com/webhook/test"
    mock_post.return_value.status_code = 200

    admin = User.objects.create_superuser(username="audit_admin_2", password="password")
    UserSSHPublicKey.objects.create(
        user=admin,
        raw_key="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA123 auditadmin",
        algorithm="ssh-ed25519",
        bits=256,
        fingerprint="SHA256:auditadmin2key",
        is_active=True,
    )

    now = timezone.now()
    req = AccessRequest.objects.create(
        requester=admin,
        key_fingerprint="SHA256:auditadmin2key",
        start_datetime=now,
        end_datetime=now + timedelta(hours=1),
        motivation="Task test",
    )

    # Test task dispatch success and non-existent
    assert dispatch_request_notification(req.id) is True
    assert dispatch_request_notification(999999) is False

    # Test task dispatch exception / retry
    mock_post.side_effect = Exception("Webhook connection error")
    with pytest.raises(Exception):
        dispatch_request_notification(req.id)

    # Test audit ingestion disallow non-POST
    client.force_login(admin)
    res_bad_method = client.get("/audit/ingest/")
    assert res_bad_method.status_code == 405

    # Test audit ingestion bad json
    res_bad_json = client.post("/audit/ingest/", data="bad_json", content_type="application/json")
    assert res_bad_json.status_code == 400

    # Test valid ingestion
    payload = {
        "host": "audit-host-1",
        "events": [{"event_type": "SYSCALL", "auid": 1001, "command": "whoami", "raw_line": "raw"}],
    }
    res_ingest = client.post(
        "/audit/ingest/", data=json.dumps(payload), content_type="application/json"
    )
    assert res_ingest.status_code == 201

    # Audit event model immutability
    event = HostAuditEvent.objects.filter(host_identifier="audit-host-1").first()
    assert str(event).startswith("[audit-host-1]")
    with pytest.raises(PermissionDenied):
        event.save()
    with pytest.raises(PermissionDenied):
        event.delete()

    # Dashboard view
    res_dash = client.get("/audit/dashboard/?host=audit-host-1&auid=1001")
    assert res_dash.status_code == 200
