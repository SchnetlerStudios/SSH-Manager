import os
import subprocess
import shutil


class POSIXProvisioner:
    """
    Stage 1 POSIX provisioner: useradd, ~/.ssh/authorized_keys (0600), visudo atomic sudoers file creation (0440).
    """

    @staticmethod
    def create_user(username: str, shell: str = "/bin/bash", comment: str = "JIT User") -> bool:
        if not username:
            raise ValueError("Username cannot be empty")
        cmd = ["useradd", "-m", "-s", shell, "-c", comment, username]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return res.returncode == 0
        except Exception:
            return False

    @staticmethod
    def setup_ssh_key(username: str, raw_key: str, home_dir: str = "") -> bool:
        if not home_dir:
            home_dir = f"/home/{username}"

        ssh_dir = os.path.join(home_dir, ".ssh")
        auth_keys_file = os.path.join(ssh_dir, "authorized_keys")

        try:
            os.makedirs(ssh_dir, mode=0o700, exist_ok=True)
            with open(auth_keys_file, "w") as f:
                f.write(f"{raw_key.strip()}\n")
            os.chmod(auth_keys_file, 0o600)
            return True
        except Exception:
            return False

    @staticmethod
    def setup_sudoers(username: str, sudoers_dir: str = "/etc/sudoers.d") -> bool:
        sudoers_file = os.path.join(sudoers_dir, username)
        tmp_file = f"{sudoers_file}.tmp"

        content = f"{username} ALL=(ALL) NOPASSWD: ALL\n"

        try:
            os.makedirs(sudoers_dir, mode=0o755, exist_ok=True)
            with open(tmp_file, "w") as f:
                f.write(content)
            os.chmod(tmp_file, 0o440)

            # Validate using visudo -cf
            res = subprocess.run(["visudo", "-cf", tmp_file], capture_output=True, text=True)
            if res.returncode == 0:
                os.replace(tmp_file, sudoers_file)
                return True
            else:
                if os.path.exists(tmp_file):
                    os.remove(tmp_file)
                return False
        except Exception:
            if os.path.exists(tmp_file):
                os.remove(tmp_file)
            return False
