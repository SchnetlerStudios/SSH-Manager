# TASKS.md - Engineering Backlog & Phase Checklist

This document breaks down the implementation into discrete, autonomous tasks. Agents (such as Jules) should pick up uncompleted tasks (`[ ]`), implement them along with their test suites, and update this document to (`[x]`).

---

## Phase 1: Control Plane Foundation & Identity/SSH Key Onboarding

- [ ] **TASK-101: Django Project Scaffolding & Multi-Environment Settings**
  - **Target Files**:
    - `control_plane/manage.py`
    - `control_plane/control_plane/settings/base.py`
    - `control_plane/control_plane/settings/development.py`
    - `control_plane/control_plane/settings/test.py`
    - `control_plane/control_plane/settings/production.py`
    - `control_plane/control_plane/urls.py`
    - `control_plane/control_plane/celery.py`
  - **Description**: Configure Django project with PostgreSQL, Celery, and split settings. `test.py` must use in-memory SQLite or test PostgreSQL with `CELERY_TASK_ALWAYS_EAGER = True`.
  - **Acceptance Tests**: `pytest control_plane` runs and passes system check.

- [ ] **TASK-102: Cryptographic SSH Key Validator & Fingerprinting Engine**
  - **Target Files**:
    - `shared/crypto_utils.py`
    - `tests/unit/test_crypto_utils.py`
  - **Description**: Implement function `validate_and_fingerprint_ssh_key(raw_key: str) -> dict`. Must parse OpenSSH public keys, reject weak algorithms (DSA, RSA < 3072 bits), accept `ssh-ed25519` and `rsa-sha2-512` ($\ge$ 3072), calculate SHA-256 fingerprint matching standard `ssh-keygen -lf` output, and extract key comments.
  - **Acceptance Tests**: Full unit test coverage covering valid Ed25519, valid 4096-bit RSA, invalid 1024-bit RSA, invalid DSA, malformed key strings.

- [ ] **TASK-103: Custom User Model & Entra ID (Azure AD) OIDC Authentication**
  - **Target Files**:
    - `control_plane/apps/authentication/models.py`
    - `control_plane/apps/authentication/utils.py`
    - `control_plane/apps/authentication/backends.py`
    - `tests/unit/test_username_sanitization.py`
    - `tests/integration/test_oidc_auth.py`
  - **Description**:
    - Create `CustomUser` model inheriting `AbstractUser` with fields: `entra_oid`, `upn`, `posix_username`.
    - Implement `sanitize_posix_username(raw_username: str) -> str` enforcing regex `^[a-z_][a-z0-9_-]{1,31}$`.
    - Custom auth backend to map Entra ID token roles (`Access.Admin` $\to$ `is_staff=True, is_superuser=True`).
  - **Acceptance Tests**: Unit tests for regex edge cases; integration tests for claim parsing with mock OIDC tokens.

- [ ] **TASK-104: Mandatory SSH Public Key Registration Gateway & Middleware**
  - **Target Files**:
    - `control_plane/apps/onboarding/models.py`
    - `control_plane/apps/onboarding/views.py`
    - `control_plane/apps/onboarding/middleware.py`
    - `control_plane/apps/onboarding/forms.py`
    - `tests/integration/test_onboarding_middleware.py`
  - **Description**:
    - Model `UserSSHPublicKey` linked to user with fingerprint, raw key, algorithm, and created timestamp.
    - Middleware `EnforceSSHKeyMiddleware`: redirects any authenticated user lacking an active public key to `/onboarding/ssh-key/`.
    - Upload view accepting public key, validating via `shared/crypto_utils.py`, and saving to database.
  - **Acceptance Tests**: Verify non-onboarded user gets 302 redirect; verify onboarded user passes through; verify invalid key shows form error.

- [ ] **TASK-105: Fleet Inventory Models & Bracketed Range Expression Parser**
  - **Target Files**:
    - `control_plane/apps/fleet/models.py`
    - `control_plane/apps/fleet/range_parser.py`
    - `tests/unit/test_range_parser.py`
    - `tests/integration/test_fleet_models.py`
  - **Description**:
    - Models: `Host` (hostname, IP/FQDN, status, mTLS cert fingerprint), `HostGroup` (name, slug, parent), `AccountSetupProfile` (shell, supplementary groups, ansible playbook path).
    - Utility `expand_host_range(pattern: str) -> list[str]`: Expands patterns like `compute-[01:05].internal` to discrete hostnames.
  - **Acceptance Tests**: Parser tests for single host, ranges (`01:20`), negative bounds handling, malformed ranges, duplicate filtering.

---

## Phase 2: Access Request Engine, Review Workflow & Teams Integration

- [ ] **TASK-201: Access Request Model & Finite State Machine (FSM)**
  - **Target Files**:
    - `control_plane/apps/access_requests/models.py`
    - `control_plane/apps/access_requests/fsm.py`
    - `tests/unit/test_request_fsm.py`
  - **Description**:
    - `AccessRequest` model with states: `PENDING`, `APPROVED`, `DENIED`, `ACTIVE`, `EXPIRED_LOCKED`, `PURGED`.
    - Fields: `requester`, `key_fingerprint`, `access_level` (`NORMAL` vs `SUDO`), `start_datetime`, `end_datetime`, `motivation`.
    - Intermediate model `HostAccessAssignment` mapping parent request to individual resolved `Host` records.
    - FSM transitions with guard conditions (e.g. `now >= start_datetime`, maximum duration $\le 7$ days).
  - **Acceptance Tests**: Unit tests asserting valid transitions and catching illegal transitions with custom exceptions.

- [ ] **TASK-202: Celery Notifications & Microsoft Teams Adaptive Cards**
  - **Target Files**:
    - `control_plane/apps/access_requests/tasks.py`
    - `control_plane/apps/access_requests/notifications.py`
    - `tests/unit/test_notifications.py`
  - **Description**:
    - Celery task `dispatch_request_notification(request_id: int)`.
    - Generates Adaptive Card JSON with request details (requester, hosts, time window, sudo level, motivation).
    - Posts payload to configured Microsoft Teams Webhook with error handling and retry policy.
  - **Acceptance Tests**: Mock HTTP post assertion verifying Adaptive Card schema, fields, and fallback to email.

- [ ] **TASK-203: Admin Review Dashboard & 1-Click Teams Deep Link Generator**
  - **Target Files**:
    - `control_plane/apps/access_requests/views.py`
    - `control_plane/apps/access_requests/utils.py`
    - `tests/unit/test_teams_deep_link.py`
    - `tests/integration/test_admin_review_view.py`
  - **Description**:
    - Utility `generate_teams_chat_url(requester_upn: str, request_id: int, host_list: list[str]) -> str`.
    - Generates deep link URL conforming to Microsoft Teams protocol.
    - Admin review dashboard view with Approve and Deny buttons protected by optimistic locking (`select_for_update`).
  - **Acceptance Tests**: Verify URL encoding of spaces/special characters; test concurrent approval race conditions.

---

## Phase 3: Host Agent & Customizable Ansible Provisioning Pipeline

- [ ] **TASK-301: Host Agent Daemon Foundation & mTLS Client**
  - **Target Files**:
    - `agent/daemon.py`
    - `agent/config.py`
    - `agent/mtls_client.py`
    - `agent/systemd/jit-host-agent.service`
    - `tests/unit/test_agent_config.py`
  - **Description**:
    - Python daemon loop running as `systemd` service.
    - mTLS client using client certificate, private key, and internal CA bundle to communicate with Control Plane API.
    - Polling mechanism with jitter and exponential backoff on network failures.
  - **Acceptance Tests**: Mock server integration test verifying client cert authentication and error handling.

- [ ] **TASK-302: Stage 1 POSIX Provisioner (User, Key & Sudoers)**
  - **Target Files**:
    - `agent/provisioner.py`
    - `tests/unit/test_agent_provisioner.py`
  - **Description**:
    - Module to invoke `useradd -m -s <shell> <username>`.
    - Atomic creation of `/home/<username>/.ssh/authorized_keys` with mode `0600` and ownership.
    - Sudoers provisioning: writes `/etc/sudoers.d/<username>` with mode `0440`, verified via `visudo -cf <file>` before saving.
  - **Acceptance Tests**: Unit tests with mock subprocess; syntax validation for generated sudoers files.

- [ ] **TASK-303: Stage 2 Ansible Runner Integration**
  - **Target Files**:
    - `agent/ansible_runner.py`
    - `tests/unit/test_ansible_runner.py`
  - **Description**:
    - Wrapper executing local Ansible playbook via `ansible-runner` or `ansible-playbook -i localhost, -c local`.
    - Supplies extra vars (`target_user`, `access_level`, `request_id`).
    - Captures stdout/stderr and sends signed execution receipt back to Django control plane.
  - **Acceptance Tests**: Mock runner test asserting command-line construction, error capture, and receipt generation.

---

## Phase 4: Account Lifecycle, Session Teardown & Irreversible Purge

- [ ] **TASK-401: Expiration Lock & Session Killer (`loginctl`)**
  - **Target Files**:
    - `agent/lifecycle.py`
    - `tests/unit/test_lifecycle_lock.py`
  - **Description**:
    - Watcher evaluating `end_datetime`.
    - Lockout sequence: `usermod -L -e 1 <username>`, truncate `authorized_keys`, remove `/etc/sudoers.d/<username>`.
    - Session termination: `loginctl terminate-user <username>` (tearing down `user-<uid>.slice`), followed by `pkill -9 -u <username>`.
  - **Acceptance Tests**: Mock subprocess assertion verifying execution order, command arguments, and failure handling.

- [ ] **TASK-402: In-Session Extension & Grace Period Re-Access**
  - **Target Files**:
    - `agent/lifecycle.py`
    - `control_plane/apps/access_requests/views.py`
    - `tests/integration/test_extension_workflow.py`
  - **Description**:
    - In-session extension updates `end_datetime` in DB; agent updates local schedule without session disruption.
    - Re-access during 3–5 day grace period unlocks account (`usermod -U -e ""`), restoring SSH key without deleting existing workspace.
  - **Acceptance Tests**: Integration test verifying zero process disruption during extension; verify workspace retention on re-access.

- [ ] **TASK-403: Irreversible 3–5 Day Purge Engine**
  - **Target Files**:
    - `agent/lifecycle.py`
    - `tests/unit/test_purge_engine.py`
  - **Description**:
    - Inspects expiration time and `/var/log/wtmp` / `lastlog`.
    - If inactivity threshold (96 hours) exceeded without active request:
      - Runs `userdel -rf <username>`.
      - Wipes crontab and mail spool.
      - Sends cryptographically signed purge receipt to Django control plane.
  - **Acceptance Tests**: Unit tests with mock filesystem and subprocess asserting full cleanup.

---

## Phase 5: Kernel Auditing (`auditd` + PAM) & Compliance

- [ ] **TASK-501: Auditd Log Parser & Immutable `auid` Telemetry Streamer**
  - **Target Files**:
    - `agent/audit_monitor.py`
    - `tests/unit/test_audit_parser.py`
  - **Description**:
    - Tails `/var/log/audit/audit.log` or listens via `audispd` plugin.
    - Parses `USER_AUTH`, `USER_START`, `USER_END`, `CRED_ACQ`, and execve calls for `/bin/su` and `/usr/bin/sudo`.
    - Extracts kernel `auid` (enforced by `pam_loginuid.so`) and correlates it back to the original Azure AD username even after root escalation.
    - Batches events and streams over mTLS to Django.
  - **Acceptance Tests**: Unit tests parsing raw hex-encoded audit logs into structured event dicts.

- [ ] **TASK-502: Django Audit Ingestion & Append-Only Compliance Log**
  - **Target Files**:
    - `control_plane/apps/audit_stream/models.py`
    - `control_plane/apps/audit_stream/views.py`
    - `tests/integration/test_audit_ingestion.py`
  - **Description**:
    - REST endpoint receiving authenticated agent audit event batches.
    - Immutable database model `HostAuditEvent` with append-only database constraints (block `UPDATE` and `DELETE`).
    - Admin compliance dashboard to filter, search, and export session command histories.
  - **Acceptance Tests**: Integration test verifying event ingestion; assert ORM update/delete raises error.

---

## Phase 6: Fleet Hardening, Packaging & Dockerized Testbed

- [ ] **TASK-601: Dockerized Fleet Testbed (Ubuntu 24.04 & Rocky Linux 9)**
  - **Target Files**:
    - `tests/docker/Dockerfile.ubuntu`
    - `tests/docker/Dockerfile.rocky`
    - `tests/docker/docker-compose.test.yml`
    - `tests/docker/run_fleet_tests.sh`
  - **Description**:
    - Multi-distribution container testbed with `systemd` enabled.
    - Allows automated testing of real `useradd`, `loginctl`, `visudo`, `auditd`, and Ansible provisioning.
  - **Acceptance Tests**: Script executes agent inside containers and validates OS changes.

- [ ] **TASK-602: CI/CD Pipeline & End-to-End Fleet Test Suite**
  - **Target Files**:
    - `.github/workflows/ci.yml`
    - `tests/integration/test_e2e_fleet.py`
  - **Description**:
    - GitHub Actions workflow running linting, unit tests, integration tests, and containerized fleet verification.
  - **Acceptance Tests**: Full CI run passes on PR or commit.
