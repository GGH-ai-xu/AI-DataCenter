# Windows Dev Launcher Design

## Goal

Provide a single Windows entry point that starts the local development environment for `server-agent`, `backend`, and `frontend`, while automatically selecting available ports.

## Scope

- Add one root batch entry point for developers.
- Add one PowerShell orchestrator script for process startup.
- Support dynamic port selection for agent, backend, and frontend.
- Inject runtime port values into backend and frontend startup commands.
- Wait for all services to become reachable before opening the browser.

## Non-Goals

- No dependency installation.
- No desktop packaging.
- No `.env` rewriting.
- No persistent config mutation.

## Entry Points

- `start-dev.bat`: user-facing Windows launcher.
- `scripts/start-dev.ps1`: port discovery, environment validation, process startup, readiness polling, and browser open.

## Startup Model

The launcher starts three processes:

1. `server-agent` with repo-root `.venv\Scripts\python.exe`
2. `backend` with the same `.venv`
3. `frontend` with `npm run dev`

The script must pick three free localhost ports before startup:

- `agentPort`
- `backendPort`
- `frontendPort`

## Runtime Injection

### Agent

- Set `GPU_AGENT_PORT=<agentPort>`
- Start from `server-agent/`

### Backend

- Set `PORT=<backendPort>`
- Set `AGENT_URL=http://127.0.0.1:<agentPort>`
- Start from `backend/`

### Frontend

- Start Vite with `--host 127.0.0.1 --port <frontendPort>`
- Set `DEV_BACKEND_URL=http://127.0.0.1:<backendPort>`
- Set `DEV_BACKEND_WS_URL=ws://127.0.0.1:<backendPort>`

## Frontend Proxy Change

`frontend/vite.config.js` must keep the current defaults for standalone use, but prefer environment variables when present:

- HTTP proxy target: `DEV_BACKEND_URL || http://localhost:8000`
- WebSocket proxy target: `DEV_BACKEND_WS_URL || ws://localhost:8000`

## Preconditions

The launcher must fail fast if any prerequisite is missing:

- `.venv\Scripts\python.exe`
- `frontend\node_modules`
- `npm`

These failures must be explicit. The launcher must not attempt silent dependency installation.

## Readiness Checks

The launcher must only report success after all three checks pass:

- `http://127.0.0.1:<agentPort>/api/health`
- `http://127.0.0.1:<backendPort>/api/health`
- `http://127.0.0.1:<frontendPort>/`

If any service does not become ready within the timeout, the script must fail and print the service name, port, and launch command.

## Testing Strategy

Add text-level regression tests that assert:

- `start-dev.bat` calls `scripts\start-dev.ps1`
- `scripts/start-dev.ps1` contains dynamic port discovery logic
- `scripts/start-dev.ps1` injects agent, backend, and frontend runtime values
- `frontend/vite.config.js` supports environment-driven proxy targets
