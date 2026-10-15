import pytest
import os
import responses
from unittest.mock import patch, MagicMock

# Agent tests
from agent.config import AgentConfig, load_config
from agent.mtls_client import MTLSClient
from agent.provisioner import POSIXProvisioner
from agent.ansible_runner import AnsibleRunnerWrapper
from agent.daemon import HostAgentDaemon
from agent.lifecycle import AccountLifecycleManager
from agent.audit_monitor import parse_audit_log_line, AuditMonitorStreamer


def test_agent_config(monkeypatch):
    monkeypatch.setenv("JIT_AGENT_HOST_IDENTIFIER", "test-node")
    monkeypatch.setenv("JIT_AGENT_POLL_INTERVAL", "5")
    cfg = load_config()
    assert cfg.host_identifier == "test-node"
    assert cfg.poll_interval == 5


@responses.activate
def test_mtls_client_poll_and_receipt(tmp_path):
    cert = tmp_path / "client.crt"
    key = tmp_path / "client.key"
    ca = tmp_path / "ca.crt"
    cert.write_text("cert")
    key.write_text("key")
    ca.write_text("ca")

    cfg = AgentConfig(
        control_plane_url="http://mock-cp.local",
        cert_path=str(cert),
        key_path=str(key),
        ca_path=str(ca),
        host_identifier="host-1",
    )
    client = MTLSClient(cfg)

    responses.add(
        responses.GET,
        "http://mock-cp.local/api/agent/jobs/?host=host-1",
        json={"jobs": [{"id": 1, "type": "PROVISION", "username": "testuser"}]},
        status=200,
    )
    jobs = client.poll_jobs()
    assert len(jobs) == 1

    responses.add(
        responses.POST,
        "http://mock-cp.local/api/agent/receipts/",
        json={"status": "received"},
        status=200,
    )
    assert client.send_receipt(1, "SUCCESS") is True


@responses.activate
def test_mtls_client_errors():
    cfg = AgentConfig(control_plane_url="http://mock-cp.local", host_identifier="host-1")
    client = MTLSClient(cfg)

    responses.add(responses.GET, "http://mock-cp.local/api/agent/jobs/?host=host-1", status=500)
    assert client.poll_jobs() == []

    responses.add(responses.POST, "http://mock-cp.local/api/agent/receipts/", status=500)
    assert not client.send_receipt(1, "FAILED")


def test_provisioner_create_user():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert POSIXProvisioner.create_user("testuser") is True

    with patch("subprocess.run", side_effect=Exception("Error")):
        assert POSIXProvisioner.create_user("testuser") is False

    with pytest.raises(ValueError):
        POSIXProvisioner.create_user("")


def test_provisioner_ssh_and_sudoers(tmp_path):
    user_home = tmp_path / "home" / "testuser"
    key_str = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA123 test@host"
    assert POSIXProvisioner.setup_ssh_key("testuser", key_str, home_dir=str(user_home)) is True

    sudoers_dir = tmp_path / "sudoers.d"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert POSIXProvisioner.setup_sudoers("testuser", sudoers_dir=str(sudoers_dir)) is True

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        assert POSIXProvisioner.setup_sudoers("failuser", sudoers_dir=str(sudoers_dir)) is False


def test_ansible_runner():
    assert AnsibleRunnerWrapper.run_playbook("", {})["success"] is False
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
        assert AnsibleRunnerWrapper.run_playbook("/pb.yml", {})["success"] is True

    with patch("subprocess.run", side_effect=Exception("Error")):
        assert AnsibleRunnerWrapper.run_playbook("/pb.yml", {})["success"] is False


def test_agent_daemon():
    daemon = HostAgentDaemon()
    job_success = {
        "id": 1,
        "type": "PROVISION",
        "username": "duser",
        "raw_key": "key",
        "access_level": "SUDO",
        "playbook_path": "/pb.yml",
    }
    with patch("agent.provisioner.POSIXProvisioner.create_user", return_value=True), \
         patch("agent.provisioner.POSIXProvisioner.setup_ssh_key", return_value=True), \
         patch("agent.provisioner.POSIXProvisioner.setup_sudoers", return_value=True), \
         patch("agent.ansible_runner.AnsibleRunnerWrapper.run_playbook", return_value={"success": True, "return_code": 0, "stdout": "", "stderr": ""}), \
         patch.object(daemon.client, "send_receipt"):
        daemon.process_job(job_success)

    with patch.object(daemon.client, "poll_jobs", return_value=[]):
        daemon.run_loop(once=True)


def test_lifecycle_manager(tmp_path):
    user_home = tmp_path / "home" / "testuser"
    ssh_dir = user_home / ".ssh"
    ssh_dir.mkdir(parents=True)
    auth_keys = ssh_dir / "authorized_keys"
    auth_keys.write_text("key")

    sudoers_dir = tmp_path / "sudoers.d"
    sudoers_dir.mkdir(parents=True)
    (sudoers_dir / "testuser").write_text("sudoers")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert AccountLifecycleManager.lock_and_terminate_session("testuser", home_dir=str(user_home), sudoers_dir=str(sudoers_dir)) is True
        assert AccountLifecycleManager.unlock_and_restore_access("testuser", "newkey", home_dir=str(user_home)) is True
        assert AccountLifecycleManager.purge_user_account("testuser") is True

    assert AccountLifecycleManager.lock_and_terminate_session("") is False
    assert AccountLifecycleManager.unlock_and_restore_access("", "") is False
    assert AccountLifecycleManager.purge_user_account("") is False


@responses.activate
def test_audit_monitor(tmp_path):
    cfg = AgentConfig(control_plane_url="http://mock-cp.local", host_identifier="host-audit")
    client = MTLSClient(cfg)
    log_file = tmp_path / "audit.log"
    log_file.write_text('type=SYSCALL auid=1001 uid=0 pid=100 exe="/bin/su" comm="su"\n')

    streamer = AuditMonitorStreamer(client, log_path=str(log_file))
    with open(log_file, "r") as f:
        events = list(streamer.process_file_lines(f))

    responses.add(
        responses.POST,
        "http://mock-cp.local/api/agent/audit-events/",
        status=201,
    )
    assert streamer.stream_batch(events) is True
