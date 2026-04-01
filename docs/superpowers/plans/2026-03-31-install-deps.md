# Install Deps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore a one-click Windows dependency installer for backend, server-agent, and frontend.

**Architecture:** Use one root batch entry point that orchestrates two focused PowerShell scripts. Keep Python environment setup and frontend package installation separated so build and launch scripts can reuse them later.

**Tech Stack:** Windows batch, PowerShell, `uv`, `npm`

---

### Task 1: Add failing tests for the install flow

**Files:**
- Create: `tests/test_install_scripts.py`

- [ ] **Step 1: Write failing tests**

Add assertions for:
- `install-deps.bat` exists and calls `scripts\setup-uv-env.ps1`
- `install-deps.bat` exists and calls `scripts\setup-frontend.ps1`
- `scripts/setup-uv-env.ps1` uses repo-root `.venv`, `uv venv`, and `uv pip install`
- `scripts/setup-frontend.ps1` runs `npm ci` under `frontend`

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest tests.test_install_scripts -v`
Expected: FAIL because the scripts do not exist yet.

### Task 2: Implement the dependency setup scripts

**Files:**
- Create: `install-deps.bat`
- Create: `scripts/setup-uv-env.ps1`
- Create: `scripts/setup-frontend.ps1`

- [ ] **Step 1: Create the batch entry point**

Call the two PowerShell scripts in sequence and propagate failure.

- [ ] **Step 2: Create the uv setup script**

Create repo-root `.venv` and install `backend/requirements.txt` plus `server-agent/requirements.txt`.

- [ ] **Step 3: Create the frontend setup script**

Run `npm ci` in `frontend/`.

- [ ] **Step 4: Re-run the script tests**

Run: `python3 -m unittest tests.test_install_scripts -v`
Expected: PASS

### Task 3: Run repository regression checks

**Files:**
- Modify: none

- [ ] **Step 1: Run the root test suite**

Run: `python3 -m unittest discover -s tests -p 'test_*.py'`
Expected: PASS
