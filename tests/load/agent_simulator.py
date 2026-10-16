"""
Fleet Agent Simulator for SSH-Manager Stress Testing.

Simulates up to 2,000 host agents performing outbound mTLS polling and receipt updates
while ensuring strict resource safety limits (CPU / Memory checks) so the test host machine
is not overloaded or brought down during testing.
"""

import time
import psutil
import logging
import concurrent.futures
from typing import List, Dict, Any, Callable, Optional

logging.basicConfig(level=logging.INFO, format="[Simulator] %(levelname)s: %(message)s")


class SystemResourceGuardError(Exception):
    """Raised when host system resource thresholds (RAM/CPU) are exceeded."""
    pass


class FleetAgentSimulator:
    def __init__(
        self,
        num_hosts: int = 2000,
        max_workers: int = 50,
        memory_threshold_percent: float = 90.0,
        cpu_threshold_percent: float = 95.0,
    ):
        self.num_hosts = num_hosts
        self.max_workers = max_workers
        self.memory_threshold_percent = memory_threshold_percent
        self.cpu_threshold_percent = cpu_threshold_percent
        self.host_identifiers = [f"sim-node-{i:04d}" for i in range(1, num_hosts + 1)]

    def check_system_safety(self) -> Dict[str, float]:
        """
        Monitors host system resources and raises SystemResourceGuardError if safety limits are exceeded.
        """
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.1)

        metrics = {
            "memory_percent": mem.percent,
            "memory_available_mb": mem.available / (1024 * 1024),
            "cpu_percent": cpu,
        }

        if mem.percent > self.memory_threshold_percent:
            raise SystemResourceGuardError(
                f"Memory safety limit exceeded! Usage: {mem.percent}% (Threshold: {self.memory_threshold_percent}%)"
            )

        if cpu > self.cpu_threshold_percent:
            raise SystemResourceGuardError(
                f"CPU safety limit exceeded! Usage: {cpu}% (Threshold: {self.cpu_threshold_percent}%)"
            )

        return metrics

    def simulate_poll_and_update(
        self,
        job_fetch_func: Callable[[str], List[Dict[str, Any]]],
        receipt_send_func: Callable[[int, str, str, str], bool],
        batch_size: int = 200,
    ) -> Dict[str, Any]:
        """
        Simulates 2,000 agents polling for jobs and sending execution receipts in batches with thread pool workers.
        """
        self.check_system_safety()
        start_time = time.time()

        processed_hosts = 0
        total_jobs_found = 0
        successful_receipts = 0

        # Process hosts in controlled batches to avoid OS resource exhaustion
        for batch_start in range(0, len(self.host_identifiers), batch_size):
            self.check_system_safety()
            batch_hosts = self.host_identifiers[batch_start : batch_start + batch_size]

            def process_host(host_id: str) -> tuple[int, int]:
                jobs = job_fetch_func(host_id)
                jobs_count = len(jobs)
                receipts_sent = 0
                for job in jobs:
                    job_id = job.get("id")
                    if job_id:
                        ok = receipt_send_func(job_id, host_id, "SUCCESS", "Simulated stress provisioning complete")
                        if ok:
                            receipts_sent += 1
                return jobs_count, receipts_sent

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                results = list(executor.map(process_host, batch_hosts))

            for jobs_count, receipts_sent in results:
                total_jobs_found += jobs_count
                successful_receipts += receipts_sent
                processed_hosts += 1

        elapsed = time.time() - start_time
        updates_per_sec = (total_jobs_found + successful_receipts) / elapsed if elapsed > 0 else 0

        return {
            "total_hosts": processed_hosts,
            "jobs_found": total_jobs_found,
            "successful_receipts": successful_receipts,
            "elapsed_seconds": round(elapsed, 3),
            "updates_per_sec": round(updates_per_sec, 2),
        }
