# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GPU 共享治理平台 — a full-stack GPU governance workbench for shared GPU environments (labs, small servers). Three independently deployed components: a Vue 3 frontend, a FastAPI backend, and a FastAPI server-agent that runs on the GPU machine. An Electron desktop shell wraps everything into a Windows installer.

Design principle: only provide conclusions based on real data; when data is insufficient, show "数据不足" rather than falling back to simulated values.

## Common Commands

### Install Dependencies
```powershell
pip install -r backend/requirements.txt
pip install -r server-agent/requirements.txt
cd frontend && npm install && cd ..
```

### Run Development (all three services)
```powershell
# Terminal 1: Agent (port 8001)
cd server-agent && python main.py

# Terminal 2: Backend (port 8000)
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 3: Frontend dev server (port 5173, proxies /api and /ws to backend)
cd frontend && npm run dev
```
Or use the one-click script: `.\start-dev.bat` / `.\launch-demo.bat`

### Build
```powershell
# Frontend production build (output to frontend/dist/, served by backend)
cd frontend && npm run build

# Windows desktop installer
.\build-windows.bat

# Python runtime only (no Electron shell)
.\build-runtime-windows.bat
```

### Test
```powershell
# Python syntax check
python -m compileall backend/app server-agent

# Python unit tests — root-level suite (14 files, ~213 cases)
python -m unittest discover -s tests -p "test_*.py"

# Run a single Python test file
python -m unittest tests.test_scheduler

# Run a single test method
python -m unittest tests.test_scheduler.TestScheduler.test_temperature_rule

# Backend-specific tests (3 files in backend/tests/)
python -m unittest discover -s backend/tests -p "test_*.py"

# Frontend unit tests (Node.js native test runner, NOT Jest/Vitest)
cd frontend && npm test

# Run a single frontend test file
cd frontend && node --test src/stores/app.test.js
```

Note: CI uses `unittest` runner. `pytest` also works locally (`python -m pytest tests/ -v`) but `unittest` is the canonical runner.

### Key URLs (after starting backend)
- UI: http://localhost:8000/
- API docs (Swagger): http://localhost:8000/docs
- Health check: http://localhost:8000/api/health

## Architecture

```
┌─────────────┐      HTTP/WS       ┌──────────────┐       HTTP        ┌──────────────┐
│  Frontend   │ ◄─────────────────► │   Backend    │ ◄───────────────► │ Server-Agent │
│  (Vue 3)    │   REST + WebSocket  │  (FastAPI)   │   REST (proxy)   │  (FastAPI)   │
│  port 5173  │                     │  port 8000   │                  │  port 8001   │
└─────────────┘                     └──────┬───────┘                  └──────────────┘
                                           │                           GPU machine
                                    SQLite (data/)                     pynvml + psutil
```

### Component Roles

**server-agent/** — Lightweight agent deployed on the GPU machine. Collects GPU metrics via `pynvml`, system metrics via `psutil`, enumerates GPU processes. Executes control actions (pause/resume/terminate processes, set power limits via nvidia-smi). Auto-falls back to simulated GPU data when no NVIDIA hardware is present. Port 8001.

**backend/** — Central orchestrator. Polls agent every 2s (`collect_loop`), stores history in SQLite, runs alert detection, scheduling engine, energy analytics, governance rules. Serves REST API + WebSocket for real-time push. Hosts the built frontend SPA from `frontend/dist/`. Port 8000.

**frontend/** — Vue 3 SPA with Vite. 8 views (Dashboard, GpuDetail, TaskManager, Scheduler, EnergyOptimization, AIAssistant, AlertCenter, MonitorCenter). State in single Pinia store (`stores/app.js`). WebSocket composable (`composables/useWebSocket.js`) for real-time data. Domain-specific data composables in `composables/`. Data transforms in `lib/`.

**desktop-shell/** — Electron wrapper (`main.js`). Manages backend+agent as child processes, handles port scanning, auto-restart, splash screen, tray icon. Builds to NSIS installer via electron-builder.

### Backend Internals

Entry point: `backend/app/main.py`. `AppState` singleton holds all services. `lifespan` context manager initializes services on startup, spawns `collect_loop` (2s interval) and `cleanup_loop` (24h, 7-day retention).

**Services** (`backend/app/services/`):
- `agent_client.py` — async HTTP client to agent
- `data_store.py` — SQLite wrapper (aiosqlite), schema auto-created via `CREATE TABLE IF NOT EXISTS`
- `scheduler.py` — hybrid rule + LLM scheduling engine, power/carbon budgets, priority-based task management
- `llm.py` — OpenAI-compatible LLM integration (default: DeepSeek), used for chat, scheduling strategies, insights, predictions
- `alert_engine.py` — threshold-based alerts (temp 85°C, power 320W, memory 90%)
- `energy_analytics.py` — KPIs, efficiency scoring, power prediction (EWA/linear/polynomial), carbon accounting
- `governance.py` — user fairness analysis, role-based rules, let-path suggestions
- `privacy.py` — username hashing (Blake2S), path/command redaction for all external responses
- `collection_pipeline.py` — data aggregation from agent
- `connection_settings.py` / `llm_settings.py` — runtime config persisted to `runtime/*.json`

**API routes** (`backend/app/api/`): 10 routers — gpu, tasks, scheduler, ai, alerts, monitor, energy, governance, system, audit. Health check and WebSocket endpoints live in main.py.

**Auth** (`backend/app/middleware/auth.py`): Bearer token (admin/observer roles). Localhost auto-trusted as admin. GET requests permissive.

### Frontend Internals

Entry + router: `frontend/src/main.js` (routes defined inline, no separate router directory). Routes lazy-loaded with `requestIdleCallback` preload for heavy views (GpuDetail, EnergyOptimization, MonitorCenter).

Pinia store (`stores/app.js`): single store using Composition API (`defineStore` with setup function). Global state for gpus, system, processes, alerts, wsConnected, per-domain request states (loading/error/data pattern via `beginDomainRequest`/`completeDomainRequest`/`failDomainRequest`). Computed summaries: `dashboardSummary`, `taskSummary`, `totalPower`, `avgTemperature`, etc.

API layer (`services/api.js`): Axios instance at `/api` base, auto-attaches Bearer token from localStorage (`gpu_gov_token`).

WebSocket (`composables/useWebSocket.js`): auto-reconnect with exponential backoff, handles `realtime` message type carrying gpus/system/processes/alerts.

Views are large single-file components (5KB–68KB). Chart components use ECharts via vue-echarts.

### Data Flow (Real-time Pipeline)

Agent GPU metrics → `AgentClient` HTTP fetch → `collect_loop` (2s) → apply task priorities → run alert engine → save to SQLite → privacy sanitization → scheduler tick (if auto) → WebSocket broadcast to all frontend clients.

### Sensitive Operations Pattern

Destructive actions (pause/resume/terminate/power-limit/schedule) use a two-phase pattern: `dry_run: true` to preview, then `acknowledge_risk: true` to execute. Pydantic models enforce input constraints (power range 100–350W, budget 400–5000W).

## Key Conventions

- **Language**: Code comments and documentation in Chinese. Commit messages use conventional commits (`feat:`, `fix:`, `build:`) with Chinese descriptions.
- **No formal linter/formatter configured** — follow existing code style.
- **No database migrations** — schemas defined with `CREATE TABLE IF NOT EXISTS` in `data_store.py`.
- **Python 3.11+**, Node.js 20+.
- **Frontend styling**: TailwindCSS 4 (via `@tailwindcss/vite` plugin). No CSS preprocessor.
- **Vendor chunking** in `vite.config.js`: `vendor-echarts`, `vendor-vue`, and `vendor` (catch-all node_modules) split manually.
- **Vite proxy**: `/api` → `http://localhost:8000`, `/ws` → `ws://localhost:8000` (configurable via `DEV_BACKEND_URL` / `DEV_BACKEND_WS_URL` env vars).
- **Runtime config files**: `runtime/connection.json` (agent URL/mode), `runtime/llm.json` (LLM settings) — persisted by backend, not committed.
- **Environment**: Copy `backend/.env.example` to `backend/.env`. Key vars: `AGENT_URL`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `POWER_BUDGET_ENABLED`, `POWER_BUDGET_WATTS`. Additional undocumented vars accepted by `main.py`: `COLLECT_INTERVAL`, `DB_PATH`, `HOST`, `PORT`, `ALERT_TEMP_THRESHOLD`, `ALERT_POWER_THRESHOLD`, `ALERT_MEMORY_THRESHOLD`, `GPU_GOV_HOME`, `RUNTIME_DIR`.
- **LLM integration**: Uses the `openai` Python SDK (OpenAI-compatible API) pointed at DeepSeek by default — not raw HTTP.
- **Test naming**: Python `test_*.py`, JS `*.test.js`.
- **Frontend test files live alongside source** (e.g., `stores/app.test.js`, `lib/realtimeSummaries.test.js`).
- **Frontend test runner**: Node.js built-in `node --test` (not Jest or Vitest). Defined as `npm test` in `package.json`.
