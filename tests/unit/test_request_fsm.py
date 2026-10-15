import pytest
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from control_plane.apps.access_requests.models import AccessRequest, AccessRequestState, AccessLevel, HostAccessAssignment
from control_plane.apps.access_requests.fsm import transition_request, TransitionNotAllowed

User = get_user_model()


@pytest.mark.django_db
def test_fsm_valid_transitions():
    user = User.objects.create_user(username="fsm_user")
    now = timezone.now()
    req = AccessRequest.objects.create(
        requester=user,
        key_fingerprint="SHA256:abc",
        access_level=AccessLevel.NORMAL,
        start_datetime=now - timedelta(minutes=5),
        end_datetime=now + timedelta(hours=2),
        motivation="Testing FSM",
        state=AccessRequestState.PENDING,
    )

    # PENDING -> APPROVED
    transition_request(req, AccessRequestState.APPROVED)
    assert req.state == AccessRequestState.APPROVED

    # APPROVED -> ACTIVE
    transition_request(req, AccessRequestState.ACTIVE)
    assert req.state == AccessRequestState.ACTIVE

    # ACTIVE -> EXPIRED_LOCKED
    transition_request(req, AccessRequestState.EXPIRED_LOCKED)
    assert req.state == AccessRequestState.EXPIRED_LOCKED

    # EXPIRED_LOCKED -> PURGED
    transition_request(req, AccessRequestState.PURGED)
    assert req.state == AccessRequestState.PURGED


@pytest.mark.django_db
def test_fsm_invalid_transition():
    user = User.objects.create_user(username="fsm_user2")
    now = timezone.now()
    req = AccessRequest.objects.create(
        requester=user,
        key_fingerprint="SHA256:abc",
        start_datetime=now,
        end_datetime=now + timedelta(hours=2),
        state=AccessRequestState.PENDING,
    )

    with pytest.raises(TransitionNotAllowed, match="Cannot transition"):
        transition_request(req, AccessRequestState.PURGED)


@pytest.mark.django_db
def test_fsm_approval_guard_duration_exceeded():
    user = User.objects.create_user(username="fsm_user3")
    now = timezone.now()
    req = AccessRequest.objects.create(
        requester=user,
        key_fingerprint="SHA256:abc",
        start_datetime=now,
        end_datetime=now + timedelta(days=10),
        state=AccessRequestState.PENDING,
    )

    with pytest.raises(TransitionNotAllowed, match="cannot exceed 7 days"):
        transition_request(req, AccessRequestState.APPROVED)


@pytest.mark.django_db
def test_fsm_activation_guard_time_window():
    user = User.objects.create_user(username="fsm_user4")
    now = timezone.now()
    # Future request
    req_future = AccessRequest.objects.create(
        requester=user,
        key_fingerprint="SHA256:abc",
        start_datetime=now + timedelta(hours=5),
        end_datetime=now + timedelta(hours=10),
        state=AccessRequestState.APPROVED,
    )
    with pytest.raises(TransitionNotAllowed, match="Cannot activate request before start_datetime"):
        transition_request(req_future, AccessRequestState.ACTIVE)

    # Past request
    req_past = AccessRequest.objects.create(
        requester=user,
        key_fingerprint="SHA256:abc",
        start_datetime=now - timedelta(hours=10),
        end_datetime=now - timedelta(hours=5),
        state=AccessRequestState.APPROVED,
    )
    with pytest.raises(TransitionNotAllowed, match="Cannot activate request past end_datetime"):
        transition_request(req_past, AccessRequestState.ACTIVE)


@pytest.mark.django_db
def test_fsm_approval_guard_invalid_datetimes():
    user = User.objects.create_user(username="fsm_user5")
    now = timezone.now()
    req = AccessRequest.objects.create(
        requester=user,
        key_fingerprint="SHA256:abc",
        start_datetime=now,
        end_datetime=now - timedelta(hours=1),
        state=AccessRequestState.PENDING,
    )
    with pytest.raises(TransitionNotAllowed, match="End datetime must be strictly after"):
        transition_request(req, AccessRequestState.APPROVED)
