# Electron Dev Launcher Design

## Goal

Provide a dedicated Windows development entry point that starts the source `server-agent`, `backend`, and `frontend`, then launches Electron against those live development services.

## Scope

- Add one root batch entry point for Electron development.
- Add one PowerShell orchestrator for dynamic port selection and startup sequencing.
- Keep the existing browser launcher unchanged.
- Teach `desktop-shell/main.js` to detect and use development service URLs instead of packaged runtimes.

## Non-Goals

- No dependency auto-installation.
- No replacement of `start-dev.bat`.
- No packaged desktop runtime changes beyond dev-mode detection.

## Entry Points

- `start-dev.bat`: browser-based web development entry.
- `start-electron-dev.bat`: Electron development entry.
- `scripts/start-electron-dev.ps1`: validates prerequisites, discovers ports, starts services, waits for readiness, then launches Electron.

## Startup Model

The Electron development launcher starts four processes:

1. `server-agent` via repo-root `.venv\Scripts\python.exe`
2. `backend` via the same virtual environment
3. `frontend` via `npm run dev`
4. `desktop-shell` via `npm run start`

The script must allocate three free localhost ports for agent, backend, and frontend before launch.

## Runtime Injection

### Agent

- `GPU_AGENT_PORT=<agentPort>`

### Backend

- `PORT=<backendPort>`
- `AGENT_URL=http://127.0.0.1:<agentPort>`

### Frontend

- `DEV_BACKEND_URL=http://127.0.0.1:<backendPort>`
- `DEV_BACKEND_WS_URL=ws://127.0.0.1:<backendPort>`
- Vite runs on `http://127.0.0.1:<frontendPort>/`

### Electron

- `DESKTOP_DEV_SERVER_URL=http://127.0.0.1:<frontendPort>/`
- `DESKTOP_DEV_BACKEND_URL=http://127.0.0.1:<backendPort>`
- `DESKTOP_DEV_AGENT_URL=http://127.0.0.1:<agentPort>`

## Electron Dev Behavior

When the Electron main process detects `DESKTOP_DEV_SERVER_URL`, it must:

- load the Vite workbench URL instead of the backend root URL
- use `DESKTOP_DEV_BACKEND_URL` and `DESKTOP_DEV_AGENT_URL` to populate runtime state
- skip packaged runtime startup and mark backend and agent as externally managed development services

If any required dev URL is missing or malformed, startup must fail explicitly.

## Validation

Regression coverage must assert:

- `start-electron-dev.bat` calls `scripts\start-electron-dev.ps1`
- `scripts/start-electron-dev.ps1` contains dynamic port discovery and Electron dev env injection
- `desktop-shell/main.js` supports dev-mode service URLs and bypasses packaged service bootstrap
