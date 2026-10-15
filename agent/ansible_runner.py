import subprocess
import json
from typing import TypedDict, Any


class AnsibleRunnerResult(TypedDict):
    success: bool
    return_code: int
    stdout: str
    stderr: str


class AnsibleRunnerWrapper:
    """
    Stage 2 Ansible runner wrapper executing setup playbooks for temporary workspaces.
    """

    @staticmethod
    def run_playbook(playbook_path: str, extra_vars: dict[str, Any]) -> AnsibleRunnerResult:
        if not playbook_path:
            return {"success": False, "return_code": -1, "stdout": "", "stderr": "No playbook path provided."}

        extra_vars_json = json.dumps(extra_vars)
        cmd = [
            "ansible-playbook",
            "-i", "localhost,",
            "-c", "local",
            playbook_path,
            "--extra-vars", extra_vars_json,
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return {
                "success": res.returncode == 0,
                "return_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr,
            }
        except Exception as e:
            return {
                "success": False,
                "return_code": -1,
                "stdout": "",
                "stderr": str(e),
            }
