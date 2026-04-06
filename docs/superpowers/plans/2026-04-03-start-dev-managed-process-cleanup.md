# Start-Dev Managed Process Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `start-dev.bat` clear stale managed `Agent`/`Backend`/`Frontend` processes from this repository before launching a new dev session.

**Architecture:** Persist the last known managed service process metadata to an ignored runtime state file, then add a startup preflight which only kills processes whose PID, executable, working directory, and command signature match this repository's managed launch pattern. Keep the cleanup logic in `scripts/dev-launch-helpers.ps1` so `scripts/start-dev.ps1` remains orchestration-only.

**Tech Stack:** PowerShell 5+, Windows `taskkill`, Python `unittest` structure tests

---

### Task 1: Lock Cleanup Contract With Tests

**Files:**
- Modify: `tests/test_install_scripts.py`
- Test: `tests/test_install_scripts.py`

- [ ] **Step 1: Write the failing test**

Add assertions that:
- `scripts/start-dev.ps1` calls a startup cleanup function before launching services.
- `scripts/dev-launch-helpers.ps1` contains a state file path under `runtime/`.
- `scripts/dev-launch-helpers.ps1` contains cleanup helpers for managed processes only.

- [ ] **Step 2: Run test to verify it fails**

Run: `timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m unittest tests.test_install_scripts -v"`
Expected: FAIL because the cleanup function and state-file logic do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Implement helper functions in `scripts/dev-launch-helpers.ps1` for:
- resolving the runtime state file path,
- matching managed service signatures,
- killing stale managed process trees,
- deleting the stale state file.

Update `scripts/start-dev.ps1` to call cleanup before starting services and save the new process state after each child process starts.

- [ ] **Step 4: Run test to verify it passes**

Run: `timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m unittest tests.test_install_scripts -v"`
Expected: PASS

### Task 2: Persist Managed Service State

**Files:**
- Modify: `scripts/dev-launch-helpers.ps1`
- Modify: `scripts/start-dev.ps1`

- [ ] **Step 1: Add runtime state helpers**

Create focused helpers for:
- `Get-ManagedServiceStatePath`
- `Save-ManagedServiceState`
- `Clear-StaleManagedServices`
- internal match helpers per managed service

- [ ] **Step 2: Record only the three managed services**

Persist entries for:
- `Agent` with `.venv\Scripts\python.exe .\main.py`
- `Backend` with `.venv\Scripts\python.exe -m uvicorn app.main:app`
- `Frontend` with `node ... npm-cli.js run dev`

- [ ] **Step 3: Keep cleanup precise**

Only kill when all of these match:
- saved PID still exists,
- executable path matches,
- working directory matches this repo,
- command line contains the expected service signature.

- [ ] **Step 4: Remove stale state on shutdown**

Extend shutdown cleanup so the runtime state file is removed when the managed dev session exits cleanly.

### Task 3: Verify Startup Behavior

**Files:**
- Modify: `tests/test_install_scripts.py`
- Verify: `scripts/start-dev.ps1`

- [ ] **Step 1: Re-run install/start script tests**

Run: `timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m unittest tests.test_install_scripts -v"`
Expected: PASS

- [ ] **Step 2: Smoke-test the PowerShell launcher**

Run a short startup verification that checks:
- stale managed-service cleanup executes before launching new services,
- unmanaged test processes are not targeted by the cleanup matcher.

- [ ] **Step 3: Capture final evidence**

Record the commands used and their pass/fail result in the task summary before closing the work.
