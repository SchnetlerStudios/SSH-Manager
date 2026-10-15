import os
from pydantic import BaseModel


class AgentConfig(BaseModel):
    control_plane_url: str = "https://localhost:8000"
    cert_path: str = "/etc/jit-agent/certs/client.crt"
    key_path: str = "/etc/jit-agent/certs/client.key"
    ca_path: str = "/etc/jit-agent/certs/ca.crt"
    poll_interval: int = 15
    host_identifier: str = "node-01"


def load_config() -> AgentConfig:
    return AgentConfig(
        control_plane_url=os.environ.get("JIT_AGENT_CONTROL_PLANE_URL", "https://localhost:8000"),
        cert_path=os.environ.get("JIT_AGENT_CERT_PATH", "/etc/jit-agent/certs/client.crt"),
        key_path=os.environ.get("JIT_AGENT_KEY_PATH", "/etc/jit-agent/certs/client.key"),
        ca_path=os.environ.get("JIT_AGENT_CA_PATH", "/etc/jit-agent/certs/ca.crt"),
        poll_interval=int(os.environ.get("JIT_AGENT_POLL_INTERVAL", "15")),
        host_identifier=os.environ.get("JIT_AGENT_HOST_IDENTIFIER", "node-01"),
    )
