from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpRequest, HttpResponse
from django.db import transaction
from django.utils import timezone
from control_plane.apps.access_requests.models import AccessRequest, AccessRequestState, HostAccessAssignment
from control_plane.apps.access_requests.fsm import transition_request
from control_plane.apps.access_requests.utils import generate_teams_chat_url
from control_plane.apps.fleet.models import Host
from control_plane.apps.fleet.range_parser import expand_host_range


@login_required
def list_access_requests_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_staff:
        requests_qs = AccessRequest.objects.all().order_by("-created_at")
    else:
        requests_qs = AccessRequest.objects.filter(requester=request.user).order_by("-created_at")

    requests_data = []
    for req in requests_qs:
        hosts = [a.host.hostname for a in req.host_assignments.all()]
        teams_url = ""
        if request.user.is_staff and req.requester.upn:
            teams_url = generate_teams_chat_url(req.requester.upn, req.id, hosts)
        requests_data.append({
            "request": req,
            "hosts": hosts,
            "teams_url": teams_url,
        })

    return render(request, "access_requests/list.html", {"requests_data": requests_data})


@login_required
def create_access_request_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        host_pattern = request.POST.get("hosts", "").strip()
        access_level = request.POST.get("access_level", "NORMAL")
        start_datetime = request.POST.get("start_datetime")
        end_datetime = request.POST.get("end_datetime")
        motivation = request.POST.get("motivation", "").strip()

        # Find user's active key
        active_key = request.user.ssh_public_keys.filter(is_active=True).first()
        if not active_key:
            return redirect("/onboarding/ssh-key/")

        expanded_hostnames = expand_host_range(host_pattern)
        matched_hosts = list(Host.objects.filter(hostname__in=expanded_hostnames))

        access_req = AccessRequest.objects.create(
            requester=request.user,
            key_fingerprint=active_key.fingerprint,
            access_level=access_level,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            motivation=motivation,
            state=AccessRequestState.PENDING,
        )

        for host in matched_hosts:
            HostAccessAssignment.objects.create(access_request=access_req, host=host)

        # Dispatch async notification
        from control_plane.apps.access_requests.tasks import dispatch_request_notification
        try:
            dispatch_request_notification.delay(access_req.id)
        except Exception:
            dispatch_request_notification.apply(args=[access_req.id])

        return redirect("/access-requests/")

    return render(request, "access_requests/create.html")


@login_required
@user_passes_test(lambda u: u.is_staff)
def review_access_request_view(request: HttpRequest, request_id: int) -> HttpResponse:
    action = request.POST.get("action")

    with transaction.atomic():
        access_req = get_object_or_404(AccessRequest.objects.select_for_update(), id=request_id)

        if access_req.state != AccessRequestState.PENDING:
            return redirect("/access-requests/")

        if action == "approve":
            transition_request(access_req, AccessRequestState.APPROVED)
            access_req.reviewed_by = request.user
            access_req.review_datetime = timezone.now()
            access_req.save()
        elif action == "deny":
            access_req.rejection_reason = request.POST.get("rejection_reason", "").strip()
            transition_request(access_req, AccessRequestState.DENIED)
            access_req.reviewed_by = request.user
            access_req.review_datetime = timezone.now()
            access_req.save()

    return redirect("/access-requests/")
