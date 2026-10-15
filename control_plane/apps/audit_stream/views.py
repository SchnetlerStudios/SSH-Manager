import json
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from control_plane.apps.audit_stream.models import HostAuditEvent


@csrf_exempt
def ingest_audit_events_view(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"error": "Only POST requests allowed"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        host_id = data.get("host", "unknown")
        events = data.get("events", [])

        audit_objects = [
            HostAuditEvent(
                host_identifier=host_id,
                event_type=e.get("event_type", "UNKNOWN"),
                auid=e.get("auid", 0),
                uid=e.get("uid"),
                euid=e.get("euid"),
                pid=e.get("pid"),
                exe=e.get("exe", ""),
                comm=e.get("comm", ""),
                command=e.get("command", ""),
                raw_line=e.get("raw_line", ""),
            )
            for e in events
        ]

        HostAuditEvent.objects.bulk_create(audit_objects)
        return JsonResponse({"status": "ingested", "count": len(audit_objects)}, status=201)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@login_required
@user_passes_test(lambda u: u.is_staff)
def compliance_audit_log_view(request: HttpRequest) -> HttpResponse:
    host_filter = request.GET.get("host", "")
    auid_filter = request.GET.get("auid", "")

    events_qs = HostAuditEvent.objects.all().order_by("-timestamp")
    if host_filter:
        events_qs = events_qs.filter(host_identifier__icontains=host_filter)
    if auid_filter and auid_filter.isdigit():
        events_qs = events_qs.filter(auid=int(auid_filter))

    events = list(events_qs[:100])
    return render(request, "audit_stream/compliance_dashboard.html", {"events": events})
