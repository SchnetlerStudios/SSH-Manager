import os
import requests
from typing import Any, Optional
from agent.config import AgentConfig


class MTLSClient:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.session = requests.Session()
        if os.path.exists(config.cert_path) and os.path.exists(config.key_path):
            self.session.cert = (config.cert_path, config.key_path)
        if os.path.exists(config.ca_path):
            self.session.verify = config.ca_path

    def poll_jobs(self) -> list[dict[str, Any]]:
        url = f"{self.config.control_plane_url}/api/agent/jobs/?host={self.config.host_identifier}"
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json().get("jobs", [])
        except Exception:
            return []

    def send_receipt(self, job_id: int, status: str, details: str = "") -> bool:
        url = f"{self.config.control_plane_url}/api/agent/receipts/"
        payload = {
            "job_id": job_id,
            "host": self.config.host_identifier,
            "status": status,
            "details": details,
        }
        try:
            resp = self.session.post(url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False
