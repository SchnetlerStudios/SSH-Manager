import time
import logging
from agent.config import load_config
from agent.mtls_client import MTLSClient
from agent.provisioner import POSIXProvisioner
from agent.ansible_runner import AnsibleRunnerWrapper

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")


class HostAgentDaemon:
    def __init__(self):
        self.config = load_config()
        self.client = MTLSClient(self.config)
        self.running = True

    def process_job(self, job: dict) -> None:
        job_id = job.get("id")
        job_type = job.get("type")
        username = job.get("username")
        raw_key = job.get("raw_key", "")
        access_level = job.get("access_level", "NORMAL")
        playbook_path = job.get("playbook_path", "")

        logging.info(f"Processing job #{job_id} ({job_type}) for user {username}")

        if job_type == "PROVISION":
            # Stage 1: POSIX User & Keys
            created = POSIXProvisioner.create_user(username)
            key_set = POSIXProvisioner.setup_ssh_key(username, raw_key)
            sudo_set = True
            if access_level == "SUDO":
                sudo_set = POSIXProvisioner.setup_sudoers(username)

            if not (created and key_set and sudo_set):
                self.client.send_receipt(job_id, "FAILED", "Stage 1 POSIX provisioning failed")
                return

            # Stage 2: Ansible Setup Profile Playbook
            if playbook_path:
                runner_res = AnsibleRunnerWrapper.run_playbook(playbook_path, {
                    "target_user": username,
                    "access_level": access_level,
                    "job_id": job_id,
                })
                if not runner_res["success"]:
                    self.client.send_receipt(job_id, "FAILED", f"Stage 2 Ansible runner failed: {runner_res['stderr']}")
                    return

            self.client.send_receipt(job_id, "SUCCESS", "Provisioning complete")

    def run_loop(self, once: bool = False):
        logging.info(f"Host agent daemon started for host '{self.config.host_identifier}'")
        while self.running:
            jobs = self.client.poll_jobs()
            for job in jobs:
                self.process_job(job)
            if once:
                break
            time.sleep(self.config.poll_interval)


if __name__ == "__main__": # pragma: no cover
    daemon = HostAgentDaemon()
    daemon.run_loop()
