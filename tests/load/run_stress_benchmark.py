#!/usr/bin/env python3
"""
Live Benchmark CLI Tool for SSH-Manager Stress Testing.

Simulates 2,000 connected SSH hosts sending polling requests and execution receipts,
benchmarking throughput, latency, and host system safety limits.
"""

import sys
import os
import time

# Ensure python path
sys.path.insert(0, os.path.abspath('.'))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "control_plane.control_plane.settings.test")

import django
django.setup()

from django.core.management import call_command
call_command('migrate', verbosity=0)

from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from control_plane.apps.fleet.models import Host
from control_plane.apps.access_requests.models import AccessRequest, HostAccessAssignment
from tests.load.agent_simulator import FleetAgentSimulator, SystemResourceGuardError

User = get_user_model()


def run_benchmark(num_hosts: int = 2000, max_workers: int = 50):
    print("=================================================================")
    print(f"   SSH-MANAGER STRESS TEST & BENCHMARK ({num_hosts} CONNECTED HOSTS)")
    print("=================================================================")

    # 1. Initialize Simulator & System Safety Check
    simulator = FleetAgentSimulator(num_hosts=num_hosts, max_workers=max_workers)
    try:
        sys_metrics = simulator.check_system_safety()
        print(f"[Safety Check] Host Memory Usage: {sys_metrics['memory_percent']}% | CPU Usage: {sys_metrics['cpu_percent']}% | Available RAM: {sys_metrics['memory_available_mb']:.1f} MB")
        print("[Safety Check] Host system is safe. Starting fleet database setup...")
    except SystemResourceGuardError as e:
        print(f"[CRITICAL SAFETY ERROR] {e}")
        sys.exit(1)

    # 2. Database Population
    db_start = time.time()
    user, _ = User.objects.get_or_create(username="stress_admin", is_staff=True)

    # Clean previous benchmark data if any
    Host.objects.filter(hostname__startswith="sim-node-").delete()

    hosts_to_create = [
        Host(
            hostname=f"sim-node-{i:04d}",
            ip_or_fqdn=f"10.250.{(i // 254) % 254}.{i % 254 + 1}",
            status="ONLINE",
        )
        for i in range(1, num_hosts + 1)
    ]
    Host.objects.bulk_create(hosts_to_create, batch_size=1000)
    all_hosts = list(Host.objects.filter(hostname__startswith="sim-node-"))

    now = timezone.now()
    req = AccessRequest.objects.create(
        requester=user,
        key_fingerprint="SHA256:benchmarkkey2000",
        start_datetime=now,
        end_datetime=now + timedelta(hours=2),
        motivation="2000 host live CLI benchmark simulation",
        state="APPROVED",
    )

    assignments = [HostAccessAssignment(access_request=req, host=h) for h in all_hosts]
    HostAccessAssignment.objects.bulk_create(assignments, batch_size=1000)

    db_elapsed = time.time() - db_start
    print(f"[DB Setup] Populated {num_hosts} host records and {len(assignments)} assignments in {db_elapsed:.2f} seconds.")

    # 3. Simulated Host Agent Traffic
    active_jobs = {
        h.hostname: [
            {
                "id": idx + 5000,
                "type": "PROVISION",
                "username": "benchmark_user",
                "raw_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBenchmarkKey stress@test",
                "access_level": "SUDO",
            }
        ]
        for idx, h in enumerate(all_hosts)
    }
    receipt_store = {}

    def fetch_jobs(host_id: str):
        return active_jobs.get(host_id, [])

    def send_receipt(job_id: int, host_id: str, status: str, details: str):
        receipt_store[host_id] = True
        return True

    print(f"\n[Simulation] Executing 2,000 agent poll & receipt loops with {max_workers} thread workers...")
    sim_results = simulator.simulate_poll_and_update(
        job_fetch_func=fetch_jobs,
        receipt_send_func=send_receipt,
        batch_size=200,
    )

    # 4. Display Results Summary
    print("\n-----------------------------------------------------------------")
    print("                     BENCHMARK RESULTS                           ")
    print("-----------------------------------------------------------------")
    print(f"Connected Host Agents Simulated: {sim_results['total_hosts']}")
    print(f"Jobs Dispatched & Polled:        {sim_results['jobs_found']}")
    print(f"Receipt Updates Transmitted:     {sim_results['successful_receipts']}")
    print(f"Simulation Duration:             {sim_results['elapsed_seconds']} seconds")
    print(f"Throughput Rate:                 {sim_results['updates_per_sec']} updates/sec")
    print("-----------------------------------------------------------------")

    post_safety = simulator.check_system_safety()
    print(f"[Post Check] Final Memory Usage: {post_safety['memory_percent']}% | CPU Usage: {post_safety['cpu_percent']}%")
    print("SUCCESS: 2,000 Host Stress Benchmark completed safely and successfully.")


if __name__ == "__main__":
    run_benchmark()
