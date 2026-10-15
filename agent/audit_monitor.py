import re
import os
import time
import logging
from typing import Any, Generator, Optional

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")


def parse_audit_log_line(line: str) -> Optional[dict[str, Any]]:
    """
    Parses auditd log line (type=SYSCALL, EXECVE, USER_AUTH, USER_START, etc.) and extracts auid, uid, exe, comm, args.
    """
    if not line or not isinstance(line, str):
        return None

    type_match = re.search(r"type=([A-Z_]+)", line)
    event_type = type_match.group(1) if type_match else "UNKNOWN"

    auid_match = re.search(r"\bauid=(\d+)", line)
    uid_match = re.search(r"\buid=(\d+)", line)
    euid_match = re.search(r"\beuid=(\d+)", line)
    pid_match = re.search(r"\bpid=(\d+)", line)
    exe_match = re.search(r'\bexe="([^"]+)"', line)
    comm_match = re.search(r'\bcomm="([^"]+)"', line)
    cmd_match = re.search(r'\bcmd="([^"]+)"', line) or re.search(r'\bCOMMAND="([^"]+)"', line)

    auid = int(auid_match.group(1)) if auid_match else None
    uid = int(uid_match.group(1)) if uid_match else None
    euid = int(euid_match.group(1)) if euid_match else None
    pid = int(pid_match.group(1)) if pid_match else None

    # Handle hex-encoded command if present
    command = cmd_match.group(1) if cmd_match else ""
    if not command and "a0=" in line:
        # Extract syscall arguments
        a_matches = re.findall(r"\ba\d+=\"?([^\s\"]+)\"?", line)
        command = " ".join(a_matches)

    return {
        "event_type": event_type,
        "auid": auid,
        "uid": uid,
        "euid": euid,
        "pid": pid,
        "exe": exe_match.group(1) if exe_match else "",
        "comm": comm_match.group(1) if comm_match else "",
        "command": command,
        "raw_line": line.strip(),
    }


class AuditMonitorStreamer:
    """
    Tails /var/log/audit/audit.log, parses auid telemetry, and streams batches over mTLS client to Django.
    """

    def __init__(self, client: Any, log_path: str = "/var/log/audit/audit.log"):
        self.client = client
        self.log_path = log_path

    def process_file_lines(self, file_obj) -> Generator[dict[str, Any], None, None]:
        for line in file_obj:
            parsed = parse_audit_log_line(line)
            if parsed and parsed.get("auid") is not None and parsed["auid"] != 4294967295:
                yield parsed

    def stream_batch(self, events: list[dict[str, Any]]) -> bool:
        if not events:
            return True
        url = f"{self.client.config.control_plane_url}/api/agent/audit-events/"
        payload = {
            "host": self.client.config.host_identifier,
            "events": events,
        }
        try:
            resp = self.client.session.post(url, json=payload, timeout=10)
            return resp.status_code == 200 or resp.status_code == 201
        except Exception:
            return False
