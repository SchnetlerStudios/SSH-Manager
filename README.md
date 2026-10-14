# SSH-Manager (JIT Linux Access Management Platform)

A Just-In-Time (JIT) Linux access management platform that deploys temporary, audited, and strictly time-bounded accounts to machines, rather than relying on bastion servers.

## Architecture Highlights

- **Centralized Control Plane (Django)**: Entra ID (OIDC) authentication, App Role mapping, mandatory SSH public key onboarding, fleet inventory, range expansion, and Celery asynchronous tasks.
- **Teams & Email Integration**: Automated Adaptive Card notifications and 1-click Microsoft Teams deep link for reviewer-to-requester chats.
- **Execution & Telemetry Plane (Host Agent)**: Decentralized, lightweight Python daemon communicating over mTLS. 2-stage provisioning with POSIX user setup and customizable Ansible playbooks (`ansible-runner`).
- **Enforced Lifecycle & Teardown**: `loginctl terminate-user` session teardown, cgroup cleanup (`user-<uid>.slice`), 3–5 day grace period, and irreversible `userdel -rf` purge.
- **Forensic Auditability**: Linux kernel `auditd` + PAM `pam_loginuid.so` tracking immutable Audit UIDs (`auid`) across `su` and `sudo` transitions.

## Documentation

Full architectural specifications, multi-phase implementation roadmap, and testing strategies are detailed in [docs/SPECIFICATION.md](docs/SPECIFICATION.md).
