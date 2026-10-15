from datetime import timedelta
from django.utils import timezone
from control_plane.apps.access_requests.models import AccessRequest, AccessRequestState


class TransitionNotAllowed(Exception):
    pass


ALLOWED_TRANSITIONS = {
    AccessRequestState.PENDING: [AccessRequestState.APPROVED, AccessRequestState.DENIED],
    AccessRequestState.APPROVED: [AccessRequestState.ACTIVE, AccessRequestState.EXPIRED_LOCKED],
    AccessRequestState.ACTIVE: [AccessRequestState.EXPIRED_LOCKED],
    AccessRequestState.EXPIRED_LOCKED: [AccessRequestState.ACTIVE, AccessRequestState.PURGED],
    AccessRequestState.DENIED: [],
    AccessRequestState.PURGED: [],
}


def transition_request(request_obj: AccessRequest, target_state: AccessRequestState) -> None:
    current = request_obj.state
    allowed = ALLOWED_TRANSITIONS.get(current, [])

    if target_state not in allowed:
        raise TransitionNotAllowed(f"Cannot transition AccessRequest #{request_obj.id} from {current} to {target_state}")

    # Guard condition validations
    now = timezone.now()

    if target_state == AccessRequestState.APPROVED:
        if request_obj.end_datetime <= request_obj.start_datetime:
            raise TransitionNotAllowed("End datetime must be strictly after start datetime.")
        if (request_obj.end_datetime - request_obj.start_datetime) > timedelta(days=7):
            raise TransitionNotAllowed("Access request duration cannot exceed 7 days.")

    if target_state == AccessRequestState.ACTIVE:
        if now < request_obj.start_datetime:
            raise TransitionNotAllowed(f"Cannot activate request before start_datetime ({request_obj.start_datetime})")
        if now > request_obj.end_datetime:
            raise TransitionNotAllowed(f"Cannot activate request past end_datetime ({request_obj.start_datetime})")

    request_obj.state = target_state
    request_obj.save()
