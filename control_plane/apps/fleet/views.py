from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from control_plane.apps.fleet.models import Host


@login_required
def disconnected_hosts_view(request):
    """
    Renders the Disconnected / Failed Hosts tab & view with status indicators in AdminLTE style.
    """
    offline_hosts = Host.objects.filter(status="OFFLINE").order_by("hostname")
    maintenance_hosts = Host.objects.filter(status="MAINTENANCE").order_by("hostname")
    all_hosts = Host.objects.all().order_by("hostname")

    context = {
        "offline_hosts": offline_hosts,
        "maintenance_hosts": maintenance_hosts,
        "all_hosts": all_hosts,
        "active_tab": "disconnected",
    }
    return render(request, "fleet/disconnected.html", context)
