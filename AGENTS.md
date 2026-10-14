# AGENTS.md - Guide for Autonomous Agents (Jules & Pair Programmers)

Welcome to the **SSH-Manager (Just-In-Time Linux Access Management Platform)** codebase. This document outlines architectural standards, folder layouts, testing mandates, and step-by-step instructions for autonomous agents (such as Jules) to pick up and implement work items independently.

---

## 1. Project Purpose & System Architecture

SSH-Manager provides time-bounded, just-in-time (JIT) access to a fleet of Linux servers without relying on persistent admin accounts or centralized root SSH keys.

The system is split into two architectural planes:
1. **Control Plane (`control_plane/`)**:
   - Built on **Python 3.11+ / Django 5+**.
   - Authenticates users via **Microsoft Entra ID (OIDC)** and maps Entra App Roles (`Access.Admin` and `Access.User`).
   - Forces **mandatory SSH public key onboarding** with cryptographic strength verification.
   - Manages fleet inventory, host groupings, and bracketed range expressions (`compute-[01:20]`).
   - Manages the **Access Request State Machine** (`PENDING` $\to$ `APPROVED` $\to$ `ACTIVE` $\to$ `EXPIRED_LOCKED` $\to$ `PURGED`).
   - Dispatches notifications via **Celery / Redis** (Teams Adaptive Cards + 1-click Teams Deep Links).
   - Ingests telemetry into an **immutable append-only audit log**.

2. **Host Agent (`agent/`)**:
   - Lightweight, standalone Python daemon running under `systemd` (`jit-host-agent.service`).
   - Polls Control Plane outbound over **mutual TLS (mTLS)**; no inbound open ports required.
   - **2-Stage Provisioning**:
     - *Stage 1*: Creates POSIX user (`useradd`), sets `~/.ssh/authorized_keys` (`0600`), validates `/etc/sudoers.d/` (`0440`).
     - *Stage 2*: Invokes `ansible-runner` to execute admin-defined custom setup playbooks.
   - **Session Teardown & Purge**:
     - At `end_datetime`, locks account (`usermod -L`), revokes keys/sudo, and invokes `loginctl terminate-user <username>` (tearing down `user-<uid>.slice`) + `pkill -9`.
     - After 3–5 days inactivity grace period, executes irreversible `userdel -rf` purge.
   - **Kernel Auditing**:
     - Tails `auditd` / PAM logs to track immutable Audit UIDs (`auid` via `pam_loginuid.so`) across `su` and `sudo` transitions, streaming structured events back to Django.

---

## 2. Directory Layout & Module Responsibilities

```
SSH-Manager/
├── AGENTS.md                  # This file: Agent instructions and operating manual
├── README.md                  # Project overview and orientation
├── pyproject.toml             # Configuration for pytest, ruff, black, mypy
├── docs/
│   ├── SPECIFICATION.md       # Canonical architectural specification & multi-phase roadmap
│   └── TASKS.md               # Actionable phase-by-phase task backlog with acceptance criteria
├── control_plane/             # Django Control Plane Web App & API
│   ├── manage.py              # Django management script
│   ├── control_plane/         # Project configuration (settings, urls, wsgi, celery)
│   │   └── settings/          # Split settings: base.py, development.py, test.py, production.py
│   ├── apps/
│   │   ├── authentication/    # Entra ID OIDC auth, user model, role claims, username sanitization
│   │   ├── onboarding/        # Mandatory SSH public key gateway, crypto validation, middleware
│   │   ├── fleet/             # Host, HostGroup models, range expansion syntax parser, setup profiles
│   │   ├── access_requests/   # Request models, FSM, Celery notifications, Teams deep link builder
│   │   └── audit_stream/      # Telemetry ingestion endpoints, append-only logs, compliance views
│   └── requirements/          # base.txt, dev.txt, test.txt
├── agent/                     # Distributed Linux Host Agent daemon
│   ├── daemon.py              # Main daemon loop (heartbeat, job polling, lifecycle evaluation)
│   ├── config.py              # Configuration loading (mTLS cert paths, poll interval, API URL)
│   ├── mtls_client.py         # Requests/httpx client configured with client cert and CA verification
│   ├── provisioner.py         # Stage 1: POSIX useradd, authorized_keys, visudo validation
│   ├── ansible_runner.py      # Stage 2: ansible-runner execution wrapper with extra-vars
│   ├── lifecycle.py           # loginctl session termination, account locking, 3-5 day purge worker
│   ├── audit_monitor.py       # auditd parser, pam_loginuid auid tracker, event streamer
│   ├── systemd/               # systemd unit file (jit-host-agent.service)
│   └── requirements.txt       # Agent runtime dependencies
├── shared/                    # Shared code between Control Plane & Host Agent
│   └── crypto_utils.py        # SSH key algorithm whitelist, parsing, SHA-256 fingerprinting
├── tests/                     # Automated Test Suites
│   ├── conftest.py            # Global pytest fixtures (mock OIDC, fake keys, sample hosts)
│   ├── unit/                  # Fast unit tests (FSM, range parser, crypto, serializers)
│   ├── integration/           # DB, Celery, REST API, middleware integration tests
│   └── docker/                # Multi-distribution container testbed (Ubuntu 24.04, Rocky Linux 9)
└── deploy/                    # Local dev & test infrastructure (docker-compose.yml, env.example)
```

---

## 3. Core Operating Rules for Autonomous Agents

When working on any task or issue in this repository, you **MUST** adhere to the following principles:

### 1. Specification Compliance
- Always read [docs/SPECIFICATION.md](docs/SPECIFICATION.md) before writing code. Do not introduce architectures or dependencies that deviate from the specification without explicit approval.
- Check [docs/TASKS.md](docs/TASKS.md) to locate the exact phase, task description, file targets, and acceptance criteria.

### 2. Testing is Mandatory (Non-Negotiable)
- **Every functional change, new feature, or bugfix must be accompanied by automated tests.**
- Do NOT consider any task done unless the corresponding test suite passes.
- Adhere to the 4-tier testing hierarchy:
  - **Tier 1 (Unit)**: Fast tests with zero external service dependencies.
  - **Tier 2 (Integration)**: Tests using test database and mock HTTP/OIDC endpoints.
  - **Tier 3 (Containerized)**: Real OS verification for host agent operations (`useradd`, `loginctl`, `sudoers`).
  - **Tier 4 (E2E)**: Full lifecycle integration.

### 3. Code Standards & Style
- **Python**: Target Python 3.11+. Follow PEP 8 guidelines.
- **Type Annotations**: Mandatory type hints on all function and method signatures.
- **Formatting & Linting**: Code must format cleanly under `black` (line length 100) and pass `ruff` / `flake8` checks without warnings.
- **Docstrings**: Document classes, public methods, and non-obvious logic using Google or Sphinx docstring style.
- **Security First**:
  - Never log, commit, or hardcode private keys, secrets, or bearer tokens.
  - Always validate subprocess commands; do not use `shell=True` when invoking system binaries (`useradd`, `usermod`, `loginctl`, `ansible-runner`).

---

## 4. Environment & Command Quick-Reference

### Virtual Environment Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r control_plane/requirements/dev.txt
pip install -r agent/requirements.txt
```

### Running Tests
```bash
# Run all unit and integration tests
pytest

# Run unit tests only
pytest tests/unit

# Run with test coverage
pytest --cov=control_plane --cov=agent --cov=shared --cov-report=term-missing

# Run Django management tests specifically
python control_plane/manage.py test --settings=control_plane.settings.test
```

### Code Formatting & Static Analysis
```bash
# Format code
black .

# Check linting
ruff check .

# Static type checking
mypy control_plane agent shared
```

### Local Services (PostgreSQL & Redis)
```bash
# Spin up local development services
docker-compose -f deploy/docker-compose.yml up -d db redis
```

---

## 5. Workflow Protocol for Working on Tasks

When picking up an item from [docs/TASKS.md](docs/TASKS.md):

1. **Locate Task & Requirements**: Read the task description, dependencies, and expected outcomes in `docs/TASKS.md`.
2. **Write Tests First (TDD)**:
   - Create or update test files in `tests/unit/` or `tests/integration/`.
   - Assert failure before implementing the feature.
3. **Implement Minimum Viable Solution**:
   - Write clean, modular, typed code in the designated directory.
   - Keep control plane code separate from host agent code.
4. **Run Verification**:
   - Execute `pytest` and confirm 100% pass rate.
   - Run `black .` and `ruff check .` to guarantee formatting.
5. **Update Task Tracking**:
   - Mark the completed item as `[x]` in `docs/TASKS.md`.
6. **Commit Changes**:
   - Use Conventional Commits format:
     - `feat(auth): implement Entra ID claim extraction and username sanitization`
     - `test(fsm): add transition tests for access request lifecycle`
     - `fix(agent): handle missing sudoers file gracefully during lockout`
