import os
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")


class AccountLifecycleManager:
    """
    Handles session termination (loginctl terminate-user + pkill -9), account locking (usermod -L),
    grace period re-access (usermod -U), and irreversible 3-5 day purge (userdel -rf).
    """

    @staticmethod
    def lock_and_terminate_session(username: str, home_dir: str = "", sudoers_dir: str = "/etc/sudoers.d") -> bool:
        if not username:
            return False

        if not home_dir:
            home_dir = f"/home/{username}"

        try:
            # 1. Lock account
            subprocess.run(["usermod", "-L", "-e", "1", username], capture_output=True, text=True)

            # 2. Blank out authorized_keys
            auth_keys = os.path.join(home_dir, ".ssh", "authorized_keys")
            if os.path.exists(auth_keys):
                with open(auth_keys, "w") as f:
                    f.write("")

            # 3. Remove sudoers file
            sudoers_file = os.path.join(sudoers_dir, username)
            if os.path.exists(sudoers_file):
                os.remove(sudoers_file)

            # 4. Terminate sessions via loginctl
            subprocess.run(["loginctl", "terminate-user", username], capture_output=True, text=True)

            # 5. Kill remaining user processes
            subprocess.run(["pkill", "-9", "-u", username], capture_output=True, text=True)

            return True
        except Exception as e:
            logging.error(f"Error locking session for {username}: {e}")
            return False

    @staticmethod
    def unlock_and_restore_access(username: str, raw_key: str, home_dir: str = "") -> bool:
        if not username or not raw_key:
            return False

        if not home_dir:
            home_dir = f"/home/{username}"

        try:
            # 1. Unlock account
            subprocess.run(["usermod", "-U", "-e", "", username], capture_output=True, text=True)

            # 2. Restore SSH authorized_keys
            ssh_dir = os.path.join(home_dir, ".ssh")
            os.makedirs(ssh_dir, mode=0o700, exist_ok=True)
            auth_keys = os.path.join(ssh_dir, "authorized_keys")
            with open(auth_keys, "w") as f:
                f.write(f"{raw_key.strip()}\n")
            os.chmod(auth_keys, 0o600)

            return True
        except Exception as e:
            logging.error(f"Error restoring access for {username}: {e}")
            return False

    @staticmethod
    def purge_user_account(username: str) -> bool:
        if not username:
            return False

        try:
            # Wipe crontab
            subprocess.run(["crontab", "-r", "-u", username], capture_output=True, text=True)

            # Irreversible user & home directory removal
            res = subprocess.run(["userdel", "-rf", username], capture_output=True, text=True)
            return res.returncode == 0 or not os.path.exists(f"/home/{username}")
        except Exception as e:
            logging.error(f"Error purging account for {username}: {e}")
            return False
