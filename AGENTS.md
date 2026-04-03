# Repository Guidelines

## Project Structure & Module Organization
`backend/app/` contains the FastAPI service, including `api/`, `services/`, `middleware/`, `models/`, and `ws/`. Runtime SQLite data lives under `backend/data/` and should stay untracked. `server-agent/` holds the host-side collector and control agent, split into `collectors/`, `controllers/`, and `main.py`. `frontend/src/` is the Vue 3 + Vite client, organized by `views/`, `components/`, `stores/`, `composables/`, `services/`, and `lib/`. `desktop-shell/` packages the Electron desktop wrapper, while `scripts/` and root `*.bat` files automate Windows development and packaging. Use `tests/` for repository-level regression checks and `backend/tests/` for backend-focused tests.

## Build, Test, and Development Commands
From `backend/`, run `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` to start the API. From `server-agent/`, run `python main.py` to launch the local GPU agent. From `frontend/`, use `npm ci`, `npm run build`, `npm run dev`, and `npm test` for install, production build, Vite dev server, and `node:test`-based frontend tests. Repository-wide checks mirror CI: `python -m compileall backend/app server-agent` and `python -m unittest discover -s tests -p "test_*.py"`. For backend service tests, use `python -m pytest backend/tests`. Windows contributors can also use `start-dev.bat`, `start-electron-dev.bat`, and `build-windows.bat`.

## Coding Style & Naming Conventions
Follow the surrounding code instead of introducing new patterns. Python uses 4-space indentation, `snake_case` modules/functions, and type-aware service classes. Vue and JavaScript files use 2-space indentation, single quotes, `PascalCase.vue` component names, and `camelCase.js` for stores, composables, and helpers. Keep comments brief and reserve them for non-obvious behavior. Prefer English identifiers, but keep user-facing Chinese labels consistent with existing UI copy.

## Testing Guidelines
Name Python tests `test_*.py` and frontend tests `*.test.js`. Place tests close to the layer they protect: `tests/` for end-to-end structure and policy checks, `backend/tests/` for API or service behavior, and `frontend/src/**` for store or transform logic. When changing behavior, update or add a regression test rather than relying on manual verification only.

## Commit & Pull Request Guidelines
Recent history mixes short Chinese summaries with Conventional Commit prefixes such as `fix:`, `build:`, and `chore:`. Prefer one focused change per commit and keep the subject brief and imperative. Pull requests should summarize the user-visible impact, list touched areas such as `backend` or `frontend`, include the commands you ran to verify the change, and attach screenshots for UI updates. Do not commit `.env` files, runtime directories, database files, or packaged artifacts.
