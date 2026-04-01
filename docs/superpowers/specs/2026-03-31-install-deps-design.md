# Windows One-Click Dependency Setup Design

## Goal

Provide a single Windows entry point that prepares all repository dependencies without starting services or building release artifacts.

## Scope

- Create one root-level batch entry point for users.
- Restore a backend setup script that uses `uv` to create and manage the repo-root `.venv`.
- Add a frontend setup script that installs `frontend/` dependencies with `npm ci`.
- Fail fast on missing tools or command failures.

## Non-Goals

- No service startup.
- No `.env` generation.
- No frontend build.
- No desktop packaging.

## Script Layout

- `install-deps.bat`: user-facing one-click entry point.
- `scripts/setup-uv-env.ps1`: creates `.venv` in repo root and installs `backend` plus `server-agent` Python dependencies with `uv`.
- `scripts/setup-frontend.ps1`: installs frontend dependencies in `frontend/` with `npm ci`.

## Behavior

`install-deps.bat` invokes the two PowerShell scripts in order. `scripts/setup-uv-env.ps1` requires `uv`, creates `.venv` when missing, and installs requirements into `.venv\Scripts\python.exe`. `scripts/setup-frontend.ps1` requires `npm` and installs from `frontend/package-lock.json` using `npm ci`.

## Validation

Add text-based regression tests that assert:

- the batch entry point calls both setup scripts;
- the Python setup script uses `uv venv` and `uv pip install` against repo-root `.venv`;
- the frontend setup script runs `npm ci` in `frontend/`.
