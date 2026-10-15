import requests
from celery import shared_task
from django.conf import settings
from control_plane.apps.access_requests.models import AccessRequest
from control_plane.apps.access_requests.notifications import build_adaptive_card_payload


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def dispatch_request_notification(self, request_id: int) -> bool:
    try:
        request_obj = AccessRequest.objects.get(id=request_id)
    except AccessRequest.DoesNotExist:
        return False

    hosts = [assignment.host.hostname for assignment in request_obj.host_assignments.all()]
    payload = build_adaptive_card_payload(request_obj, hosts)

    webhook_url = getattr(settings, "TEAMS_WEBHOOK_URL", "")
    if not webhook_url:
        return True

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as exc:
        raise self.retry(exc=exc)
