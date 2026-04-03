# GPU Import Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pre-console GPU import workflow that scans local or remote hardware, persists the selected GPU scope, and makes the control console display and govern only the imported cards.

**Architecture:** Introduce a backend `ImportContextService` as the single source of truth for imported GPU scope, add system APIs for scan/import/reset/current-context, and thread the selected GPU indexes through control, monitoring, governance, and energy surfaces. On the frontend, add a dedicated `/import` route and import UI, shift app gating from “agent connected” to “valid import context”, and strip connection-switching UI out of the console pages so `Dashboard.vue` becomes a pure management homepage.

**Tech Stack:** FastAPI, Pydantic, existing `AgentClient` and `DataStore`, Vue 3 with `<script setup>`, Pinia, existing `node:test` frontend tests, Python `unittest` repo tests, Vite build verification.

---

## File Map

**Create:**
- `backend/app/services/import_context.py`
  Purpose: persist the current imported GPU scope, validate runtime availability, filter GPU/process data, and guard out-of-scope control actions.
- `tests/test_import_context.py`
  Purpose: lock import-context persistence, filtering, and invalidation behavior with fast unit tests.
- `tests/test_import_control_scope.py`
  Purpose: lock backend control-surface filtering and out-of-scope action rejection at the API/service edge.
- `tests/test_import_history_scope.py`
  Purpose: lock scoped historical queries in `DataStore` and keep imported-GPU filtering from regressing in energy/monitoring paths.
- `tests/test_import_layer_structure.py`
  Purpose: lock the frontend routing split, dedicated import view, and “console without connection center” structure.
- `frontend/src/views/ImportWorkspace.vue`
  Purpose: host the full import flow (`source -> scan -> choose GPUs -> import`).
- `frontend/src/components/import/ImportSourcePanel.vue`
  Purpose: render local/remote mode selection, remote address input, scan button, and scan feedback.
- `frontend/src/components/import/ImportHardwareSummary.vue`
  Purpose: render CPU and system summary returned from the scan API.
- `frontend/src/components/import/ImportGpuGrid.vue`
  Purpose: render selectable GPU cards and emit the selected indexes list.
- `frontend/src/lib/importContext.js`
  Purpose: hold small pure helpers for validating import state and formatting imported GPU labels.
- `frontend/src/lib/importContext.test.js`
  Purpose: keep import-context helper behavior covered by `node:test`.

**Modify:**
- `backend/app/models/schemas.py`
  Purpose: add request models for scan/import payloads.
- `backend/app/main.py`
  Purpose: load `ImportContextService`, expose it on `app_state`, scope collection-loop broadcasts and auto-governance to imported GPUs, and include import readiness in `/api/health`.
- `backend/app/api/system.py`
  Purpose: add import-context APIs and move startup readiness toward import-based gating.
- `backend/app/api/gpu.py`
  Purpose: filter realtime and history responses to the imported GPU scope.
- `backend/app/api/tasks.py`
  Purpose: filter process lists and reject task actions on out-of-scope processes.
- `backend/app/api/scheduler.py`
  Purpose: scope scheduler status and guard manual/AI scheduling actions to imported GPUs only.
- `backend/app/api/ai.py`
  Purpose: build chat/control context from imported GPUs and imported processes only.
- `backend/app/api/monitor.py`
  Purpose: scope system-adjacent monitoring outputs, user stats, and replay/timeline data to imported GPUs.
- `backend/app/api/alerts.py`
  Purpose: scope visible alert history to imported GPUs.
- `backend/app/api/energy.py`
  Purpose: pass imported GPU indexes into energy calculations and history endpoints.
- `backend/app/api/governance.py`
  Purpose: scope fairness analysis and exported governance reports to imported GPUs.
- `backend/app/middleware/auth.py`
  Purpose: mark import-context mutation routes as admin-only POST/DELETE APIs.
- `backend/app/services/ai_control.py`
  Purpose: build and execute AI actions only within the imported GPU scope.
- `backend/app/services/scheduler.py`
  Purpose: re-check imported scope during action execution, even when callers forget to guard.
- `backend/app/services/energy_analytics.py`
  Purpose: accept optional GPU indexes and thread them to history queries.
- `backend/app/services/governance.py`
  Purpose: accept optional GPU indexes and calculate fairness only on imported GPUs.
- `backend/app/services/data_store.py`
  Purpose: add optional `gpu_indexes` filters to history, alerts, timeline, replay, and user-stats queries.
- `frontend/src/main.js`
  Purpose: add the `/import` route and preload the import view with the rest of the app shell.
- `frontend/src/App.vue`
  Purpose: replace “agent connected” route locking with “valid import context” gating.
- `frontend/src/services/api.js`
  Purpose: expose import-context scan/read/commit/reset APIs.
- `frontend/src/stores/app.js`
  Purpose: store the current import context and derive console readiness from it.
- `frontend/src/views/Dashboard.vue`
  Purpose: remove the connection-center UI and become a pure imported-GPU control homepage.
- `frontend/src/composables/useDashboardData.js`
  Purpose: drop dashboard connection-refresh plumbing that no longer belongs to the console homepage.
- `frontend/src/components/app/AppPrimarySidebar.vue`
  Purpose: update sidebar copy so it reflects imported scope rather than connection setup.
- `tests/test_frontend_ui_structure.py`
  Purpose: update or replace the old “dashboard as access center” assumptions.

---

### Task 1: Lock Import-Context Persistence And Filtering With Red Tests

**Files:**
- Create: `tests/test_import_context.py`
- Test: `tests/test_import_context.py`

- [ ] **Step 1: Write failing unit tests for the new backend import-context service**

Create `tests/test_import_context.py` with the following content:

```python
import os
import sys
import tempfile
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.import_context import ImportContextService  # noqa: E402


class ImportContextServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.tempdir.name, "import-context.json")
        self.service = ImportContextService(
            self.config_path,
            "http://127.0.0.1:8001",
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_save_import_persists_selected_gpu_indexes_and_snapshot(self):
        self.service.load()

        saved = self.service.save_import(
            source_mode="remote",
            agent_url="http://10.0.0.8:8001",
            agent_label="实验室 A",
            gpu_indexes=[0, 2],
            system_info={
                "cpu_percent": 12.5,
                "cpu_count": 32,
                "memory_total": 256000,
            },
            gpus=[
                {"index": 0, "name": "RTX 4090", "temperature": 62, "power_usage": 280, "memory_used": 4096, "memory_total": 24564, "gpu_utilization": 88, "timestamp": 1.0},
                {"index": 2, "name": "RTX 6000", "temperature": 55, "power_usage": 210, "memory_used": 2048, "memory_total": 49140, "gpu_utilization": 64, "timestamp": 1.0},
            ],
        )

        self.assertEqual(saved["source_mode"], "remote")
        self.assertEqual(saved["agent_label"], "实验室 A")
        self.assertEqual(saved["imported_gpu_indexes"], [0, 2])
        self.assertTrue(saved["valid"])

        reloaded = ImportContextService(self.config_path, "http://127.0.0.1:8001").load()
        self.assertEqual(reloaded["imported_gpu_indexes"], [0, 2])
        self.assertEqual(reloaded["snapshot"]["gpus"][1]["index"], 2)

    def test_filter_helpers_only_keep_imported_scope(self):
        self.service.load()
        self.service.save_import(
            source_mode="local",
            agent_url="http://127.0.0.1:8001",
            agent_label="本机 Agent",
            gpu_indexes=[1],
            system_info={"cpu_percent": 18.0, "cpu_count": 16, "memory_total": 128000},
            gpus=[
                {"index": 1, "name": "RTX 4080", "temperature": 58, "power_usage": 240, "memory_used": 2048, "memory_total": 16384, "gpu_utilization": 72, "timestamp": 1.0},
            ],
        )

        filtered_gpus = self.service.filter_gpus([
            {"index": 0, "name": "GPU0"},
            {"index": 1, "name": "GPU1"},
            {"index": 2, "name": "GPU2"},
        ])
        filtered_processes = self.service.filter_processes([
            {"pid": 11, "gpu_index": 1, "command": "train.py"},
            {"pid": 22, "gpu_index": 0, "command": "other.py"},
        ])

        self.assertEqual([gpu["index"] for gpu in filtered_gpus], [1])
        self.assertEqual([proc["pid"] for proc in filtered_processes], [11])

    def test_validate_runtime_marks_context_invalid_when_selected_gpu_disappears(self):
        self.service.load()
        self.service.save_import(
            source_mode="remote",
            agent_url="http://10.0.0.8:8001",
            agent_label="实验室 A",
            gpu_indexes=[0, 1],
            system_info={"cpu_percent": 22.0, "cpu_count": 32, "memory_total": 256000},
            gpus=[
                {"index": 0, "name": "RTX 4090", "temperature": 62, "power_usage": 280, "memory_used": 4096, "memory_total": 24564, "gpu_utilization": 88, "timestamp": 1.0},
                {"index": 1, "name": "RTX 4090", "temperature": 60, "power_usage": 260, "memory_used": 4096, "memory_total": 24564, "gpu_utilization": 81, "timestamp": 1.0},
            ],
        )

        snapshot = self.service.validate_runtime(
            {"status": "ok"},
            [{"index": 0, "name": "RTX 4090"}],
        )

        self.assertFalse(snapshot["valid"])
        self.assertIn("GPU 1", snapshot["invalid_reason"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify the new service is still missing**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_import_context -v"
```

Expected:

- FAIL with `ModuleNotFoundError` because `app.services.import_context` does not exist yet

- [ ] **Step 3: Commit the red tests**

```bash
git add tests/test_import_context.py
git commit -m "test: add import context service coverage"
```

---

### Task 2: Implement ImportContextService, Health Readiness, And Import APIs

**Files:**
- Create: `backend/app/services/import_context.py`
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/system.py`
- Modify: `backend/app/middleware/auth.py`
- Test: `tests/test_import_context.py`
- Test: `tests/test_connection_settings.py`

- [ ] **Step 1: Create the backend import-context service**

Create `backend/app/services/import_context.py` with this implementation:

```python
from __future__ import annotations

import json
import os
import time


class ImportContextService:
    def __init__(self, config_path: str, default_local_url: str):
        self.config_path = config_path
        self.default_local_url = default_local_url.rstrip("/")
        self._state = self._empty_state()

    def _empty_state(self) -> dict:
        return {
            "source_mode": "local",
            "agent_url": self.default_local_url,
            "agent_label": "本机 Agent",
            "imported_gpu_indexes": [],
            "imported_at": None,
            "snapshot": {"system": None, "gpus": []},
            "valid": False,
            "invalid_reason": "尚未导入任何 GPU",
        }

    def _ensure_parent(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

    def _persist(self):
        self._ensure_parent()
        with open(self.config_path, "w", encoding="utf-8") as handle:
            json.dump(self._state, handle, ensure_ascii=False, indent=2)

    def load(self) -> dict:
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            self._state = {**self._empty_state(), **payload}
        else:
            self._persist()
        return self.snapshot()

    def snapshot(self) -> dict:
        return json.loads(json.dumps(self._state, ensure_ascii=False))

    def selected_gpu_indexes(self) -> list[int]:
        return [int(item) for item in self._state.get("imported_gpu_indexes") or []]

    def save_import(
        self,
        source_mode: str,
        agent_url: str,
        agent_label: str,
        gpu_indexes: list[int],
        system_info: dict | None,
        gpus: list[dict],
    ) -> dict:
        selected = sorted({int(item) for item in gpu_indexes})
        self._state = {
            "source_mode": source_mode,
            "agent_url": agent_url.rstrip("/"),
            "agent_label": (agent_label or "").strip() or ("本机 Agent" if source_mode == "local" else "远程 Agent"),
            "imported_gpu_indexes": selected,
            "imported_at": time.time(),
            "snapshot": {
                "system": system_info or None,
                "gpus": [gpu for gpu in gpus if int(gpu.get("index", -1)) in selected],
            },
            "valid": True,
            "invalid_reason": "",
        }
        self._persist()
        return self.snapshot()

    def clear(self, reason: str = "已清空导入上下文") -> dict:
        self._state = self._empty_state()
        self._state["invalid_reason"] = reason
        self._persist()
        return self.snapshot()

    def mark_invalid(self, reason: str) -> dict:
        self._state["valid"] = False
        self._state["invalid_reason"] = reason
        self._persist()
        return self.snapshot()

    def validate_runtime(self, agent_health: dict | None, gpus: list[dict]) -> dict:
        if not self.selected_gpu_indexes():
            return self.clear("尚未导入任何 GPU")
        if not agent_health:
            return self.mark_invalid("当前导入目标不可达，需要重新导入")

        gpu_indexes = {int(item.get("index", -1)) for item in gpus}
        missing = [index for index in self.selected_gpu_indexes() if index not in gpu_indexes]
        if missing:
            return self.mark_invalid(f"已导入的 GPU {', '.join(f'GPU {index}' for index in missing)} 不再存在")

        self._state["valid"] = True
        self._state["invalid_reason"] = ""
        self._persist()
        return self.snapshot()

    def filter_gpus(self, gpus: list[dict]) -> list[dict]:
        selected = set(self.selected_gpu_indexes())
        return [gpu for gpu in gpus if int(gpu.get("index", -1)) in selected]

    def filter_processes(self, processes: list[dict]) -> list[dict]:
        selected = set(self.selected_gpu_indexes())
        return [proc for proc in processes if int(proc.get("gpu_index", -1)) in selected]

    def ensure_gpu_allowed(self, gpu_index: int):
        if int(gpu_index) not in set(self.selected_gpu_indexes()):
            raise ValueError(f"GPU {gpu_index} 不在当前导入范围内，请重新导入管理卡")

    def ensure_process_allowed(self, pid: int, processes: list[dict]):
        allowed = {int(proc.get("pid", -1)) for proc in self.filter_processes(processes)}
        if int(pid) not in allowed:
            raise ValueError(f"PID {pid} 不在当前导入范围内，请重新导入管理卡")
```

- [ ] **Step 2: Add import request models and wire the service into app startup**

Append these request models to `backend/app/models/schemas.py` right after `ConnectionConfigRequest`:

```python
class ImportScanRequest(BaseModel):
    mode: str = Field(default="local", pattern=r"^(local|remote)$")
    agent_url: Optional[str] = Field(default=None, max_length=300)
    agent_label: str = Field(default="", max_length=120)


class ImportCommitRequest(BaseModel):
    mode: str = Field(default="local", pattern=r"^(local|remote)$")
    agent_url: Optional[str] = Field(default=None, max_length=300)
    agent_label: str = Field(default="", max_length=120)
    gpu_indexes: list[int] = Field(default_factory=list, min_length=1)
```

Update the top of `backend/app/main.py`:

```python
from app.services.import_context import ImportContextService
```

Extend `AppState`:

```python
    import_context: ImportContextService
```

Initialize and load it inside `lifespan()` after `connection_settings` is loaded:

```python
    import_config_path = os.getenv(
        "IMPORT_CONTEXT_PATH",
        os.path.join(runtime_dir, "import-context.json"),
    )

    app_state.import_context = ImportContextService(
        import_config_path,
        app_state.connection.default_local_url,
    )
    app_state.import_context.load()
```

Update `/api/health` in `backend/app/main.py`:

```python
    gpus = await app_state.agent.get_all_gpus() if agent_health else []
    import_context = app_state.import_context.validate_runtime(agent_health, gpus)
    return {
        "status": "ok",
        "agent_connected": agent_health is not None,
        "agent_info": agent_health,
        "ws_connections": ws_manager.connection_count,
        "llm_available": app_state.llm is not None,
        "connection": app_state.connection.snapshot(agent_health),
        "import_context": import_context,
        "workspace_ready": bool(import_context.get("valid")),
        "llm": app_state.llm_settings.snapshot(app_state.llm is not None),
    }
```

Update `backend/app/middleware/auth.py` so admin-only writes also include the new import routes:

```python
    "/api/system/import-context",
```

Also pass the import context into `SchedulerEngine` when it is constructed in `backend/app/main.py`:

```python
    app_state.scheduler = SchedulerEngine(
        app_state.agent,
        app_state.store,
        app_state.llm,
        app_state.privacy,
        app_state.import_context,
        budget_limit_watts=int(os.getenv("POWER_BUDGET_WATTS", "1200")),
        budget_enabled=os.getenv("POWER_BUDGET_ENABLED", "false").lower() in {"1", "true", "yes", "on"},
    )
```

- [ ] **Step 3: Add scan/read/commit/reset import endpoints**

Update imports in `backend/app/api/system.py`:

```python
from app.models.schemas import (
    ConnectionConfigRequest,
    ImportCommitRequest,
    ImportScanRequest,
    LLMConfigRequest,
)
```

Add these endpoints near the connection routes:

```python
@router.get("/import-context")
async def get_import_context():
    from app.main import app_state

    agent_health = await app_state.agent.health_check()
    gpus = await app_state.agent.get_all_gpus() if agent_health else []
    return app_state.import_context.validate_runtime(agent_health, gpus)


@router.post("/import-context/scan")
async def scan_import_context(req: ImportScanRequest):
    from app.main import app_state
    from app.services.agent_client import AgentClient

    try:
        mode, target_url = app_state.connection.resolve_target(req.mode, req.agent_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    health = await app_state.connection.probe(target_url)
    if not health:
        return {
            "success": False,
            "mode": mode,
            "agent_url": target_url,
            "agent_label": req.agent_label or ("本机 Agent" if mode == "local" else "远程 Agent"),
            "message": "无法连接到目标 Agent",
            "system": None,
            "gpus": [],
        }

    probe_client = AgentClient(target_url)
    try:
        system_info = await probe_client.get_system_info()
        gpus = await probe_client.get_all_gpus()
    finally:
        await probe_client.close()

    return {
        "success": True,
        "mode": mode,
        "agent_url": target_url,
        "agent_label": req.agent_label or ("本机 Agent" if mode == "local" else "远程 Agent"),
        "message": "扫描成功",
        "agent_health": health,
        "system": system_info,
        "gpus": gpus,
    }


@router.post("/import-context")
async def commit_import_context(req: ImportCommitRequest):
    from app.main import app_state

    try:
        connection = await app_state.connection.update(
            app_state.agent,
            req.mode,
            req.agent_url,
            req.agent_label,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not connection.get("connected"):
        raise HTTPException(status_code=400, detail="目标 Agent 不可达，无法完成导入")

    system_info = await app_state.agent.get_system_info()
    gpus = await app_state.agent.get_all_gpus()
    available = {int(item.get("index", -1)) for item in gpus}
    missing = [index for index in req.gpu_indexes if int(index) not in available]
    if missing:
        raise HTTPException(status_code=400, detail=f"GPU {missing} 当前不存在，无法导入")

    context = app_state.import_context.save_import(
        source_mode=connection["mode"],
        agent_url=connection["agent_url"],
        agent_label=connection["agent_label"],
        gpu_indexes=req.gpu_indexes,
        system_info=system_info,
        gpus=gpus,
    )
    return {
        "success": True,
        "message": "导入完成，控制台已切换到选中的 GPU",
        "import_context": context,
    }


@router.delete("/import-context")
async def reset_import_context():
    from app.main import app_state

    snapshot = app_state.import_context.clear("用户主动触发重新导入")
    return {"success": True, "import_context": snapshot}
```

This intentionally reuses `ConnectionSettingsService.update()` so the imported local/remote target survives restart, while the console itself no longer exposes connection switching.

- [ ] **Step 4: Run the service tests again and keep the existing connection tests green**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_import_context tests.test_connection_settings -v"
```

Expected:

- PASS for all tests in `tests.test_import_context`
- PASS for all tests in `tests.test_connection_settings`

- [ ] **Step 5: Commit the backend import-context foundation**

```bash
git add backend/app/services/import_context.py backend/app/models/schemas.py backend/app/main.py backend/app/api/system.py backend/app/middleware/auth.py tests/test_import_context.py
git commit -m "feat: add persisted import context APIs"
```

---

### Task 3: Scope Realtime Control Surfaces And Block Out-Of-Scope Actions

**Files:**
- Create: `tests/test_import_control_scope.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/gpu.py`
- Modify: `backend/app/api/tasks.py`
- Modify: `backend/app/api/scheduler.py`
- Modify: `backend/app/api/ai.py`
- Modify: `backend/app/services/ai_control.py`
- Modify: `backend/app/services/scheduler.py`
- Test: `tests/test_import_control_scope.py`
- Test: `tests/test_scheduler.py`

- [ ] **Step 1: Write failing tests for realtime filtering and action guards**

Create `tests/test_import_control_scope.py` with the following content:

```python
import os
import sys
import types
import unittest
from unittest import mock


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.api.gpu import get_realtime  # noqa: E402
from app.api.tasks import get_tasks, pause_task  # noqa: E402
from app.models.schemas import TaskActionRequest  # noqa: E402


class FakeAgent:
    async def get_all_gpus(self):
        return [{"index": 0, "name": "GPU0"}, {"index": 1, "name": "GPU1"}]

    async def get_system_info(self):
        return {"cpu_percent": 10}

    async def get_processes(self):
        return [
            {"pid": 10, "gpu_index": 0, "command": "python a.py", "priority": "normal"},
            {"pid": 11, "gpu_index": 1, "command": "python b.py", "priority": "normal"},
        ]

    async def pause_task(self, pid):
        return {"success": True, "pid": pid}


class FakeStore:
    async def get_all_task_priorities(self):
        return {10: "normal", 11: "urgent"}

    async def save_audit_log(self, **kwargs):
        return None


class FakePrivacy:
    def sanitize_processes(self, processes):
        return processes


class FakeImportContext:
    def filter_gpus(self, gpus):
        return [gpu for gpu in gpus if gpu["index"] == 1]

    def filter_processes(self, processes):
        return [proc for proc in processes if proc["gpu_index"] == 1]

    def ensure_process_allowed(self, pid, processes):
        allowed = {proc["pid"] for proc in self.filter_processes(processes)}
        if pid not in allowed:
            raise ValueError(f"PID {pid} 不在当前导入范围内")


class ImportControlScopeTests(unittest.IsolatedAsyncioTestCase):
    async def test_gpu_realtime_only_returns_imported_gpus(self):
        fake_main = types.SimpleNamespace(
            app_state=types.SimpleNamespace(
                agent=FakeAgent(),
                import_context=FakeImportContext(),
            )
        )

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            payload = await get_realtime()

        self.assertEqual([item["index"] for item in payload["gpus"]], [1])
        self.assertEqual(payload["system"]["cpu_percent"], 10)

    async def test_tasks_list_only_returns_imported_gpu_processes(self):
        fake_main = types.SimpleNamespace(
            app_state=types.SimpleNamespace(
                agent=FakeAgent(),
                store=FakeStore(),
                privacy=FakePrivacy(),
                import_context=FakeImportContext(),
            )
        )

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            payload = await get_tasks()

        self.assertEqual([item["pid"] for item in payload["processes"]], [11])
        self.assertEqual(payload["processes"][0]["priority"], "urgent")

    async def test_pause_task_rejects_pid_outside_import_scope(self):
        fake_main = types.SimpleNamespace(
            app_state=types.SimpleNamespace(
                agent=FakeAgent(),
                store=FakeStore(),
                privacy=FakePrivacy(),
                import_context=FakeImportContext(),
            )
        )

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            with self.assertRaisesRegex(Exception, "当前导入范围内"):
                await pause_task(TaskActionRequest(pid=10, acknowledge_risk=True))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify filtering and guards are still missing**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_import_control_scope -v"
```

Expected:

- FAIL because `get_realtime()` still returns all GPUs
- FAIL because `get_tasks()` still returns all GPU processes
- FAIL because `pause_task()` still has no import-scope guard

- [ ] **Step 3: Thread import-context filtering through realtime GPU, task, scheduler, and AI surfaces**

Update `backend/app/api/gpu.py`:

```python
@router.get("/realtime")
async def get_realtime():
    from app.main import app_state

    gpus = await app_state.agent.get_all_gpus()
    gpus = app_state.import_context.filter_gpus(gpus)
    system = await app_state.agent.get_system_info()
    return {"gpus": gpus, "system": system}


@router.get("/history/{gpu_index}")
async def get_history(gpu_index: int, hours: float = Query(default=1.0, ge=0.1, le=168)):
    from app.main import app_state

    app_state.import_context.ensure_gpu_allowed(gpu_index)
    data = await app_state.store.get_gpu_history(gpu_index, hours)
    return {"gpu_index": gpu_index, "hours": hours, "data": data}


@router.get("/summary")
async def get_power_summary(hours: float = Query(default=24.0, ge=1, le=168)):
    from app.main import app_state

    gpu_indexes = app_state.import_context.selected_gpu_indexes()
    return await app_state.store.get_power_summary(hours, gpu_indexes=gpu_indexes)
```

Update `backend/app/api/tasks.py` so process reads and actions stay in-scope:

```python
@router.get("/")
async def get_tasks():
    from app.main import app_state

    processes = await app_state.agent.get_processes()
    processes = app_state.import_context.filter_processes(processes)
    priorities = await app_state.store.get_all_task_priorities()
    for proc in processes:
        proc["priority"] = priorities.get(proc["pid"], "normal")
    return {"processes": app_state.privacy.sanitize_processes(processes)}


async def _apply_task_action(req: TaskActionRequest, label: str, action_name: str):
    from app.main import app_state

    _ensure_risk_acknowledged(req, label)
    processes = await app_state.agent.get_processes()
    app_state.import_context.ensure_process_allowed(req.pid, processes)
    action_map = {
        "pause_task": app_state.agent.pause_task,
        "resume_task": app_state.agent.resume_task,
        "terminate_task": app_state.agent.terminate_task,
    }


@router.post("/priority")
async def set_priority(req: TaskPriorityUpdate):
    from app.main import app_state

    processes = await app_state.agent.get_processes()
    app_state.import_context.ensure_process_allowed(req.pid, processes)
    await app_state.store.set_task_priority(req.pid, req.priority)
    return {"success": True, "pid": req.pid, "priority": req.priority}
```

Update `backend/app/api/scheduler.py`:

```python
@router.get("/status")
async def get_scheduler_status():
    from app.main import app_state
    from app.services.scheduler import get_time_period, get_time_period_label

    gpus = app_state.import_context.filter_gpus(await app_state.agent.get_all_gpus())
    return {
        "auto_enabled": app_state.scheduler.auto_enabled,
        "time_period": get_time_period(),
        "time_period_label": get_time_period_label(),
        "budget": app_state.scheduler.get_budget_status(gpus),
        "carbon": app_state.scheduler.get_carbon_budget_status(gpus or []),
    }


@router.post("/power-limit")
async def manual_power_limit(req: PowerLimitRequest):
    from app.main import app_state
    if not req.acknowledge_risk:
        raise HTTPException(status_code=400, detail="真实限功率操作需要先确认风险")
    app_state.import_context.ensure_gpu_allowed(req.gpu_index)
    app_state.scheduler.clear_managed_gpu(req.gpu_index)
    result = await app_state.agent.set_power_limit(req.gpu_index, req.power_limit)
    result["applied"] = bool(result.get("success"))
    return result


@router.post("/run-once")
async def run_schedule_once(req: ScheduleRunRequest | None = Body(default=None)):
    from app.main import app_state
    req = req or ScheduleRunRequest()
    if not req.acknowledge_risk:
        raise HTTPException(status_code=400, detail="真实调度执行需要先确认风险")

    gpus = app_state.import_context.filter_gpus(await app_state.agent.get_all_gpus())
    processes = app_state.import_context.filter_processes(await app_state.agent.get_processes())

    if not gpus:
        return {"error": "当前导入范围内无法获取 GPU 数据"}

    rule_actions = await app_state.scheduler.run_rules(gpus, processes)
    rule_results = await app_state.scheduler.execute_actions(rule_actions) if rule_actions else []

    budget_actions = await app_state.scheduler.run_budget_schedule(gpus, processes)
    budget_results = await app_state.scheduler.execute_actions(budget_actions) if budget_actions else []

    ai_strategy = await app_state.scheduler.run_ai_schedule(gpus, processes)
    ai_results = await app_state.scheduler.execute_actions(ai_strategy["actions"]) if ai_strategy and "actions" in ai_strategy else []

    latest_gpus = app_state.import_context.filter_gpus(await app_state.agent.get_all_gpus())
    return {
        "rule_actions": rule_actions,
        "rule_results": rule_results,
        "budget_actions": budget_actions,
        "budget_results": budget_results,
        "ai_strategy": ai_strategy,
        "ai_results": ai_results,
        "budget": app_state.scheduler.get_budget_status(latest_gpus or gpus),
        "carbon": app_state.scheduler.get_carbon_budget_status(latest_gpus or gpus),
    }


@router.get("/evaluation")
async def get_schedule_evaluation():
    from app.main import app_state

    cached = app_state.scheduler._last_evaluation
    if cached:
        return {"evaluation": cached, "source": "cached"}

    gpus = app_state.import_context.filter_gpus(await app_state.agent.get_all_gpus())
    if not gpus:
        return {"evaluation": None, "message": "当前导入范围内暂无 GPU 数据，无法评估"}

    result = await app_state.scheduler.evaluate_last_schedule(gpus)
    if result:
        return {"evaluation": result, "source": "realtime"}

    return {
        "evaluation": {
            "score": 0,
            "verdict": "暂无评估",
            "effective_actions": [],
            "ineffective_actions": [],
            "suggestions": ["请先在当前导入范围内执行一次调度，系统将自动评估调度效果"],
        },
        "source": "none",
    }


@router.get("/report")
async def generate_report():
    from app.main import app_state

    gpu_indexes = app_state.import_context.selected_gpu_indexes()
    summary = await app_state.store.get_power_summary(24, gpu_indexes=gpu_indexes)
    alerts = await app_state.store.get_alerts(limit=20, gpu_indexes=gpu_indexes)

    if app_state.llm:
        report = await app_state.llm.generate_report(summary, alerts)
        if report and not str(report).startswith("报告生成失败"):
            return {"report": report, "source": "llm"}

    return {
        "report": build_fallback_report(summary, alerts),
        "source": "fallback",
    }
```

Update `backend/app/api/ai.py` to build context from imported scope:

```python
    gpus = app_state.import_context.filter_gpus(await app_state.agent.get_all_gpus())
    system = await app_state.agent.get_system_info()
    processes = app_state.import_context.filter_processes(await app_state.agent.get_processes())
    processes = app_state.privacy.sanitize_processes(processes)
```

Update `backend/app/services/ai_control.py`:

```python
async def build_control_context(app_state) -> dict:
    gpus = app_state.import_context.filter_gpus(await app_state.agent.get_all_gpus() or [])
    processes = app_state.import_context.filter_processes(await app_state.agent.get_processes() or [])
```

And guard execution inside `execute_control_actions()`:

```python
            if act == "set_power_limit":
                app_state.import_context.ensure_gpu_allowed(target["gpu_index"])
                app_state.scheduler.clear_managed_gpu(target["gpu_index"])
                response = await app_state.agent.set_power_limit(
                    target["gpu_index"],
                    target["power_limit"],
                )
            elif act in {"pause_task", "resume_task", "terminate_task"}:
                app_state.import_context.ensure_process_allowed(target["pid"], context["processes"])
```

Update `backend/app/services/scheduler.py` so even indirect callers are guarded and every schedule log is stamped with the imported GPU scope:

```python
    def __init__(
        self,
        agent_client,
        data_store,
        llm_service=None,
        privacy_service=None,
        import_context=None,
        budget_limit_watts: int = 1200,
        budget_enabled: bool = False,
    ):
        self.agent = agent_client
        self.store = data_store
        self.llm = llm_service
        self.privacy = privacy_service
        self.import_context = import_context
        self._last_schedule_time = 0
        self._schedule_interval = 300
        self._auto_enabled = False
        self._last_actions = None
        self._last_gpu_state = None
        self._last_evaluation = None

    async def execute_actions(self, actions: list[dict]) -> list[dict]:
        scope = self.import_context.selected_gpu_indexes() if self.import_context else None
        results = []
        for action in actions:
            act = action.get("action")
            target = action.get("target", {})
            reason = action.get("reason", "")
            result = {
                "action": act,
                "target": target,
                "reason": reason,
                "success": False,
            }
            if act == "set_power_limit":
                if self.import_context:
                    self.import_context.ensure_gpu_allowed(target["gpu_index"])
                resp = await self.agent.set_power_limit(
                    target["gpu_index"],
                    target["power_limit"],
                )
                result["success"] = resp.get("success", False)
            elif act == "pause_task":
                current_processes = await self.agent.get_processes()
                if self.import_context:
                    self.import_context.ensure_process_allowed(target["pid"], current_processes)
                resp = await self.agent.pause_task(target["pid"])
                result["success"] = resp.get("success", False)
            elif act == "resume_task":
                current_processes = await self.agent.get_processes()
                if self.import_context:
                    self.import_context.ensure_process_allowed(target["pid"], current_processes)
                resp = await self.agent.resume_task(target["pid"])
                result["success"] = resp.get("success", False)

            result["applied"] = bool(result["success"])
            await self.store.save_schedule_log(
                act,
                json.dumps(target),
                reason,
                "success" if result["success"] else "failed",
                gpu_indexes=scope,
            )
            results.append(result)
        return results

    async def evaluate_last_schedule(self, current_gpus: list[dict]) -> Optional[dict]:
        if not self.llm or not self._last_actions or not self._last_gpu_state:
            return None
        from app.services.llm import EVALUATE_PROMPT

        result = await self.llm.evaluate_schedule(
            EVALUATE_PROMPT.format(
                actions=json.dumps(self._last_actions, indent=2, ensure_ascii=False),
                before_state=json.dumps(self._last_gpu_state, indent=2, ensure_ascii=False),
                after_state=json.dumps(current_gpus, indent=2, ensure_ascii=False),
            )
        )
        if not result:
            return None
        self._last_evaluation = result
        scope = self.import_context.selected_gpu_indexes() if self.import_context else None
        await self.store.save_schedule_log(
            "ai_evaluate",
            json.dumps({"evaluation": result}),
            result.get("verdict", ""),
            "success",
            gpu_indexes=scope,
        )
```

Update `backend/app/main.py` `collect_loop()` so automatic storage, alerts, scheduler tick, and WebSocket payloads are all limited to the imported GPUs:

```python
            import_context = app_state.import_context.validate_runtime(
                {"status": "ok"} if gpus else None,
                gpus,
            )
            scoped_gpus = (
                app_state.import_context.filter_gpus(gpus)
                if import_context.get("valid")
                else []
            )
            scoped_processes = (
                app_state.import_context.filter_processes(enriched_processes)
                if import_context.get("valid")
                else []
            )
            alerts = app_state.alert_engine.check_all_gpus(scoped_gpus)

            await app_state.store.save_collection_cycle(
                scoped_gpus,
                scoped_processes,
                alerts,
            )

            public_processes = app_state.privacy.sanitize_processes(scoped_processes)
            await asyncio.gather(
                app_state.scheduler.tick(scoped_gpus, scoped_processes),
                ws_manager.broadcast({
                    "type": "realtime",
                    "gpus": scoped_gpus,
                    "system": system,
                    "processes": public_processes,
                    "alerts": alerts,
                    "import_context": import_context,
                }),
            )
```

- [ ] **Step 4: Run the new scope tests and keep scheduler behavior green**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_import_control_scope tests.test_scheduler -v"
```

Expected:

- PASS for `tests.test_import_control_scope`
- PASS for `tests.test_scheduler`

- [ ] **Step 5: Commit realtime scope enforcement**

```bash
git add backend/app/main.py backend/app/api/gpu.py backend/app/api/tasks.py backend/app/api/scheduler.py backend/app/api/ai.py backend/app/services/ai_control.py backend/app/services/scheduler.py tests/test_import_control_scope.py
git commit -m "feat: scope realtime control surfaces to imported GPUs"
```

---

### Task 4: Scope Historical Queries, Energy Analytics, Governance, Alerts, And Monitoring

**Files:**
- Create: `tests/test_import_history_scope.py`
- Modify: `backend/app/services/data_store.py`
- Modify: `backend/app/services/energy_analytics.py`
- Modify: `backend/app/services/governance.py`
- Modify: `backend/app/api/monitor.py`
- Modify: `backend/app/api/alerts.py`
- Modify: `backend/app/api/energy.py`
- Modify: `backend/app/api/governance.py`
- Test: `tests/test_import_history_scope.py`

- [ ] **Step 1: Write failing tests for scoped historical queries**

Create `tests/test_import_history_scope.py` with the following content:

```python
import os
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

from fastapi import HTTPException


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.api.alerts import acknowledge_alert  # noqa: E402
from app.services.data_store import DataStore  # noqa: E402


class ImportHistoryScopeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tempdir.name, "history.db")
        self.store = DataStore(self.db_path)
        await self.store.init()
        now = time.time()

        await self.store.save_gpu_snapshot([
            {"index": 0, "temperature": 60, "power_usage": 200, "power_limit": 320, "gpu_utilization": 80, "memory_utilization": 50, "memory_used": 4096, "memory_total": 24564, "fan_speed": 30, "timestamp": now},
            {"index": 1, "temperature": 55, "power_usage": 150, "power_limit": 320, "gpu_utilization": 60, "memory_utilization": 40, "memory_used": 2048, "memory_total": 24564, "fan_speed": 25, "timestamp": now},
        ])
        await self.store.track_processes([
            {"pid": 101, "gpu_index": 0, "username": "alice", "command": "train_a.py", "gpu_memory_used": 4096},
            {"pid": 202, "gpu_index": 1, "username": "bob", "command": "train_b.py", "gpu_memory_used": 2048},
        ], timestamp=now)
        self.alert_zero_id = await self.store.save_alert(
            {"gpu_index": 0, "alert_type": "temperature", "severity": "warning", "message": "GPU0 hot", "value": 88, "threshold": 85, "timestamp": now}
        )
        self.alert_one_id = await self.store.save_alert(
            {"gpu_index": 1, "alert_type": "power", "severity": "warning", "message": "GPU1 high power", "value": 280, "threshold": 250, "timestamp": now}
        )
        await self.store.save_schedule_log(
            "set_power_limit",
            '{"gpu_index": 0, "power_limit": 220}',
            "scope zero",
            "success",
            gpu_indexes=[0],
        )
        await self.store.save_schedule_log(
            "set_power_limit",
            '{"gpu_index": 1, "power_limit": 200}',
            "scope one",
            "success",
            gpu_indexes=[1],
        )
        await self.store.save_optimization_snapshot(
            {
                "baseline_power": 200,
                "optimized_power": 140,
                "saving_pct": 30,
                "co2_saved_kg": 0.03,
                "actions_json": "[]",
                "scope_gpu_indexes": [0],
            }
        )
        await self.store.save_optimization_snapshot(
            {
                "baseline_power": 150,
                "optimized_power": 120,
                "saving_pct": 20,
                "co2_saved_kg": 0.02,
                "actions_json": "[]",
                "scope_gpu_indexes": [1],
            }
        )

    async def asyncTearDown(self):
        await self.store.close()
        self.tempdir.cleanup()

    async def test_power_summary_accepts_gpu_scope(self):
        summary = await self.store.get_power_summary(hours=1, gpu_indexes=[1])

        self.assertEqual([item["gpu_index"] for item in summary["gpus"]], [1])
        self.assertEqual(round(summary["total_avg_power"], 1), 150.0)

    async def test_alerts_accept_gpu_scope(self):
        alerts = await self.store.get_alerts(limit=10, gpu_indexes=[0])

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["gpu_index"], 0)

    async def test_process_timeline_accepts_gpu_scope(self):
        timeline = await self.store.get_process_timeline(hours=1, gpu_indexes=[1])

        self.assertEqual([item["pid"] for item in timeline], [202])

    async def test_schedule_history_accepts_exact_scope(self):
        logs = await self.store.get_schedule_history(hours=1, limit=10, gpu_indexes=[1])

        self.assertEqual([item["reason"] for item in logs], ["scope one"])

    async def test_optimization_history_accepts_exact_scope(self):
        history = await self.store.get_optimization_history(hours=1, gpu_indexes=[0])

        self.assertEqual(len(history), 1)
        self.assertEqual(round(history[0]["optimized_power"], 1), 140.0)

    async def test_replay_frames_accept_gpu_scope(self):
        frames = await self.store.get_replay_frames(hours=1, bucket_minutes=10, gpu_indexes=[0])

        active = [item for item in frames if item["gpu_count"]]
        self.assertTrue(active)
        self.assertEqual(active[0]["gpu_count"], 1)
        self.assertEqual(round(active[0]["avg_power"], 1), 200.0)


class AlertRouteScopeTests(unittest.IsolatedAsyncioTestCase):
    async def test_acknowledge_alert_rejects_out_of_scope_alert(self):
        fake_store = types.SimpleNamespace(
            get_alert_by_id=mock.AsyncMock(return_value={"id": 9, "gpu_index": 7}),
            acknowledge_alert=mock.AsyncMock(),
        )

        class FakeImportContext:
            def ensure_gpu_allowed(self, gpu_index: int):
                raise ValueError(f"GPU {gpu_index} 不在当前导入范围内，请重新导入管理卡")

        fake_main = types.SimpleNamespace(
            app_state=types.SimpleNamespace(
                store=fake_store,
                import_context=FakeImportContext(),
            )
        )

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            with self.assertRaises(HTTPException) as ctx:
                await acknowledge_alert(9)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("当前导入范围内", ctx.exception.detail)
        fake_store.acknowledge_alert.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify the historical query methods still lack GPU scope parameters**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_import_history_scope -v"
```

Expected:

- FAIL because `save_schedule_log()`, `get_schedule_history()`, `get_optimization_history()`, and `get_replay_frames()` do not support scope-aware signatures yet
- FAIL because `acknowledge_alert()` still allows confirming alerts outside the imported GPU scope

- [ ] **Step 3: Add scope persistence to `DataStore` and thread imported indexes into history, alerts, energy, governance, and replay**

Update `backend/app/services/data_store.py` in four focused pieces.

1. Extend the schema and add compatibility migration for existing SQLite files:

```python
CREATE TABLE IF NOT EXISTS schedule_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    reason TEXT NOT NULL,
    result TEXT,
    scope_gpu_indexes_json TEXT NOT NULL DEFAULT '[]',
    timestamp REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS optimization_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    baseline_power REAL,
    optimized_power REAL,
    saving_pct REAL,
    co2_saved_kg REAL,
    actions_json TEXT,
    scope_gpu_indexes_json TEXT NOT NULL DEFAULT '[]',
    timestamp REAL NOT NULL
);

    async def init(self):
        await self._db.executescript(_INIT_SQL)
        for statement in (
            "ALTER TABLE schedule_log ADD COLUMN scope_gpu_indexes_json TEXT NOT NULL DEFAULT '[]'",
            "ALTER TABLE optimization_snapshots ADD COLUMN scope_gpu_indexes_json TEXT NOT NULL DEFAULT '[]'",
        ):
            try:
                await self._db.execute(statement)
            except aiosqlite.OperationalError:
                pass
        await self._db.commit()
```

2. Add reusable helpers for row-level GPU filters and exact-scope filters:

```python
    @staticmethod
    def _normalize_gpu_indexes(gpu_indexes: list[int] | None) -> list[int]:
        if not gpu_indexes:
            return []
        return sorted({int(item) for item in gpu_indexes})

    @classmethod
    def _gpu_where_clause(cls, column: str, gpu_indexes: list[int] | None) -> tuple[str, list[int]]:
        indexes = cls._normalize_gpu_indexes(gpu_indexes)
        if not indexes:
            return "", []
        placeholders = ",".join("?" for _ in indexes)
        return f" AND {column} IN ({placeholders})", indexes

    @classmethod
    def _scope_json(cls, gpu_indexes: list[int] | None) -> str:
        return json.dumps(cls._normalize_gpu_indexes(gpu_indexes), ensure_ascii=False)

    @classmethod
    def _scope_where_clause(cls, column: str, gpu_indexes: list[int] | None) -> tuple[str, list[str]]:
        indexes = cls._normalize_gpu_indexes(gpu_indexes)
        if not indexes:
            return "", []
        return f" AND {column} = ?", [cls._scope_json(indexes)]
```

3. Update scope-aware read/write methods in `backend/app/services/data_store.py`:

```python
    async def get_all_gpu_latest(self, gpu_indexes: list[int] | None = None) -> list[dict]:
        clause, params = self._gpu_where_clause("gpu_index", gpu_indexes)
        cursor = await self._db.execute(
            f"""SELECT * FROM gpu_history
               WHERE id IN (
                   SELECT MAX(id) FROM gpu_history GROUP BY gpu_index
               ){clause}
               ORDER BY gpu_index""",
            tuple(params),
        )

    async def get_power_summary(self, hours: float = 24.0, gpu_indexes: list[int] | None = None) -> dict:
        since = time.time() - hours * 3600
        clause, params = self._gpu_where_clause("gpu_index", gpu_indexes)
        cursor = await self._db.execute(
            f"""SELECT gpu_index,
                      AVG(power_usage) as avg_power,
                      MAX(power_usage) as max_power,
                      MIN(power_usage) as min_power,
                      COUNT(*) as samples
               FROM gpu_history
               WHERE timestamp >= ?{clause}
               GROUP BY gpu_index""",
            (since, *params),
        )

    async def get_alerts(self, limit: int = 100, unack_only: bool = False, gpu_indexes: list[int] | None = None) -> list[dict]:
        base_where = "WHERE acknowledged = 0" if unack_only else "WHERE 1=1"
        clause, params = self._gpu_where_clause("gpu_index", gpu_indexes)
        cursor = await self._db.execute(
            f"SELECT * FROM alerts {base_where}{clause} ORDER BY timestamp DESC LIMIT ?",
            (*params, limit),
        )

    async def get_alert_by_id(self, alert_id: int) -> dict | None:
        cursor = await self._db.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_process_timeline(self, hours: float = 24.0, gpu_indexes: list[int] | None = None) -> list[dict]:
        since = time.time() - hours * 3600
        clause, params = self._gpu_where_clause("gpu_index", gpu_indexes)
        cursor = await self._db.execute(
            f"""SELECT * FROM process_history
               WHERE last_seen >= ?{clause}
               ORDER BY first_seen DESC""",
            (since, *params),
        )

    async def get_hourly_power_aggregation(self, hours: float = 24.0, gpu_indexes: list[int] | None = None) -> list[dict]:
        since = time.time() - hours * 3600
        clause, params = self._gpu_where_clause("gpu_index", gpu_indexes)
        cursor = await self._db.execute(
            f"""SELECT
                   CAST(strftime('%H', datetime(timestamp, 'unixepoch', 'localtime')) AS INTEGER) as hour,
                   AVG(power_usage) as avg_power,
                   MAX(power_usage) as max_power,
                   MIN(power_usage) as min_power,
                   SUM(power_usage) as total_power,
                   COUNT(*) as samples,
                   AVG(gpu_utilization) as avg_util,
                   AVG(temperature) as avg_temp
               FROM gpu_history
               WHERE timestamp >= ?{clause}
               GROUP BY hour
               ORDER BY hour""",
            (since, *params),
        )

    async def get_hourly_power_series(self, hours: float = 72.0, gpu_indexes: list[int] | None = None) -> list[dict]:
        since = time.time() - hours * 3600
        clause, params = self._gpu_where_clause("gpu_index", gpu_indexes)
        cursor = await self._db.execute(
            f"""SELECT
                   CAST((timestamp / 3600) AS INTEGER) * 3600 as hour_ts,
                   AVG(power_usage) as avg_power,
                   MAX(power_usage) as max_power,
                   MIN(power_usage) as min_power,
                   COUNT(*) as samples
               FROM gpu_history
               WHERE timestamp >= ?{clause}
               GROUP BY hour_ts
               ORDER BY hour_ts""",
            (since, *params),
        )

    async def get_user_stats(self, gpu_indexes: list[int] | None = None) -> list[dict]:
        clause, params = self._gpu_where_clause("gpu_index", gpu_indexes)
        cursor = await self._db.execute(
            f"""SELECT username,
                      COUNT(*) AS task_count,
                      MIN(first_seen) AS earliest_start
               FROM process_history
               WHERE is_active = 1{clause}
               GROUP BY username
               ORDER BY task_count DESC, username""",
            tuple(params),
        )

    async def save_schedule_log(
        self,
        action: str,
        target: str,
        reason: str,
        result: str = "",
        gpu_indexes: list[int] | None = None,
    ):
        scope_json = self._scope_json(gpu_indexes)
        await self._db.execute(
            """INSERT INTO schedule_log
               (action, target, reason, result, scope_gpu_indexes_json, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (action, target, reason, result, scope_json, time.time()),
        )
        await self._db.commit()

    async def save_optimization_snapshot(self, data: dict, gpu_indexes: list[int] | None = None):
        scope_json = self._scope_json(gpu_indexes or data.get("scope_gpu_indexes"))
        await self._db.execute(
            """INSERT INTO optimization_snapshots
               (baseline_power, optimized_power, saving_pct, co2_saved_kg, actions_json, scope_gpu_indexes_json, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("baseline_power", 0),
                data.get("optimized_power", 0),
                data.get("saving_pct", 0),
                data.get("co2_saved_kg", 0),
                data.get("actions_json", "[]"),
                scope_json,
                time.time(),
            ),
        )
        await self._db.commit()

    async def get_optimization_history(self, hours: float = 72.0, gpu_indexes: list[int] | None = None) -> list[dict]:
        since = time.time() - hours * 3600
        clause, params = self._scope_where_clause("scope_gpu_indexes_json", gpu_indexes)
        cursor = await self._db.execute(
            f"""SELECT * FROM optimization_snapshots
               WHERE timestamp >= ?{clause}
                 AND COALESCE(baseline_power, 0) >= 0
                 AND COALESCE(optimized_power, 0) >= 0
               ORDER BY timestamp DESC LIMIT 50""",
            (since, *params),
        )

    async def get_schedule_history(
        self,
        hours: float = 72.0,
        limit: int = 50,
        gpu_indexes: list[int] | None = None,
    ) -> list[dict]:
        since = time.time() - hours * 3600
        clause, params = self._scope_where_clause("scope_gpu_indexes_json", gpu_indexes)
        cursor = await self._db.execute(
            f"""SELECT * FROM schedule_log
               WHERE timestamp >= ?{clause}
               ORDER BY timestamp DESC LIMIT ?""",
            (since, *params, limit),
        )

    async def get_replay_frames(
        self,
        hours: float = 24.0,
        bucket_minutes: int = 10,
        gpu_indexes: list[int] | None = None,
    ) -> list[dict]:
        bucket_seconds = max(60, int(bucket_minutes) * 60)
        now = time.time()
        since = now - hours * 3600
        start_bucket = int(since // bucket_seconds) * bucket_seconds
        end_bucket = int(now // bucket_seconds) * bucket_seconds
        frames = build_frame_index(start_bucket, end_bucket, bucket_seconds)
        gpu_clause, gpu_params = self._gpu_where_clause("gpu_index", gpu_indexes)
        scope_clause, scope_params = self._scope_where_clause("scope_gpu_indexes_json", gpu_indexes)
        gpu_rows = await self._fetch_rows(
            f"""SELECT CAST(timestamp / ? AS INTEGER) * ? AS bucket_ts,
                      AVG(power_usage) AS avg_power,
                      AVG(gpu_utilization) AS avg_util,
                      AVG(memory_utilization) AS avg_memory_util,
                      AVG(power_limit) AS avg_power_limit,
                      MAX(temperature) AS max_temp,
                      COUNT(DISTINCT gpu_index) AS gpu_count
               FROM gpu_history
               WHERE timestamp >= ?{gpu_clause}
               GROUP BY bucket_ts
               ORDER BY bucket_ts""",
            (bucket_seconds, bucket_seconds, since, *gpu_params),
        )
        alert_rows = await self._fetch_rows(
            f"""SELECT CAST(timestamp / ? AS INTEGER) * ? AS bucket_ts,
                      COUNT(*) AS alert_count,
                      SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END) AS critical_alert_count
               FROM alerts
               WHERE timestamp >= ?{gpu_clause}
               GROUP BY bucket_ts
               ORDER BY bucket_ts""",
            (bucket_seconds, bucket_seconds, since, *gpu_params),
        )
        schedule_rows = await self._fetch_rows(
            f"""SELECT action, reason, result, timestamp
               FROM schedule_log
               WHERE timestamp >= ?{scope_clause}
               ORDER BY timestamp ASC""",
            (since, *scope_params),
        )
        process_rows = await self._fetch_rows(
            f"""SELECT username, first_seen, last_seen
               FROM process_history
               WHERE last_seen >= ?{gpu_clause}
               ORDER BY first_seen ASC""",
            (since, *gpu_params),
        )
```

4. Thread the imported GPU indexes through services and routes that currently read all history:

`backend/app/services/energy_analytics.py`

```python
    async def get_energy_metrics(self, hours: float = 24.0, gpu_indexes: list[int] | None = None) -> dict:
        summary = await self.store.get_power_summary(hours, gpu_indexes=gpu_indexes)
        latest = await self.store.get_all_gpu_latest(gpu_indexes=gpu_indexes)

    async def get_optimization_analysis(self, gpu_indexes: list[int] | None = None) -> dict:
        latest = await self.store.get_all_gpu_latest(gpu_indexes=gpu_indexes)
        live_gpus = await self.agent.get_all_gpus() if self.agent else []
        if gpu_indexes:
            allowed = set(int(item) for item in gpu_indexes)
            live_gpus = [gpu for gpu in live_gpus if int(gpu.get("index", -1)) in allowed]
        current_gpus = live_gpus or latest
        current_total = sum(g.get("power_usage", 0) for g in current_gpus)
        ai_suggestions = []
        estimated_saving_w = 0
        optimized_power = max(0, current_total - estimated_saving_w)
        saving_pct = (estimated_saving_w / current_total * 100) if current_total > 0 else 0
        co2_saved = estimated_saving_w / 1000 * CARBON_FACTOR
        await self.store.save_optimization_snapshot(
            {
                "baseline_power": current_total,
                "optimized_power": optimized_power,
                "saving_pct": saving_pct,
                "co2_saved_kg": co2_saved,
                "actions_json": json.dumps(ai_suggestions, ensure_ascii=False),
            },
            gpu_indexes=gpu_indexes,
        )
```

Use the same `gpu_indexes` argument for every public read method that currently operates on all GPUs:

- `get_time_period_breakdown`
- `get_gpu_efficiency`
- `get_power_prediction`
- `get_carbon_data`
- `get_full_report`
- `get_schedule_history`
- `get_history_comparison`
- `generate_export_report`
- `get_ai_insight`
- `get_ai_anomaly_analysis`
- `get_strategy_benchmark`

`backend/app/services/governance.py`

```python
    async def get_fairness_report(self, gpu_indexes: list[int] | None = None) -> dict:
        gpus = await self.agent.get_all_gpus() or []
        processes = await self.agent.get_processes() or []
        if gpu_indexes:
            allowed = set(int(item) for item in gpu_indexes)
            gpus = [gpu for gpu in gpus if int(gpu.get("index", -1)) in allowed]
            processes = [proc for proc in processes if int(proc.get("gpu_index", -1)) in allowed]
        history_stats = await self.store.get_user_stats(gpu_indexes=gpu_indexes)
```

And:

```python
    async def generate_export_report(self, fmt: str = "markdown", gpu_indexes: list[int] | None = None) -> str:
        report = await self.get_fairness_report(gpu_indexes=gpu_indexes)
```

Update the API routes to pass the imported indexes:

`backend/app/api/monitor.py`

```python
    gpu_indexes = app_state.import_context.selected_gpu_indexes()
    processes = app_state.import_context.filter_processes(await app_state.agent.get_processes())
    db_stats = await app_state.store.get_user_stats(gpu_indexes=gpu_indexes)
    timeline = await app_state.store.get_process_timeline(hours, gpu_indexes=gpu_indexes)
    frames = await app_state.store.get_replay_frames(hours, bucket_minutes, gpu_indexes=gpu_indexes)
```

`backend/app/api/alerts.py`

```python
from fastapi import APIRouter, HTTPException, Query

    alerts = await app_state.store.get_alerts(
        limit,
        unack_only,
        gpu_indexes=app_state.import_context.selected_gpu_indexes(),
    )


@router.post("/acknowledge/{alert_id}")
async def acknowledge_alert(alert_id: int):
    from app.main import app_state

    alert = await app_state.store.get_alert_by_id(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    try:
        app_state.import_context.ensure_gpu_allowed(alert["gpu_index"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await app_state.store.acknowledge_alert(alert_id)
    return {"success": True, "alert_id": alert_id}
```

`backend/app/api/energy.py`

```python
    gpu_indexes = app_state.import_context.selected_gpu_indexes()
    return await app_state.energy.get_energy_metrics(hours, gpu_indexes=gpu_indexes)
```

Apply the same pattern to every route in `backend/app/api/energy.py`, including `/optimize`, `/optimization-history`, `/schedule-history`, `/history-comparison`, and `/export-report`.

`backend/app/api/governance.py`

```python
    gpu_indexes = app_state.import_context.selected_gpu_indexes()
    report = await app_state.governance.get_fairness_report(gpu_indexes=gpu_indexes)
```

And:

```python
    content = await app_state.governance.generate_export_report(format, gpu_indexes=gpu_indexes)
```

Inside `export_full_governance_report()` apply the same imported scope to every sub-call:

```python
    gpu_indexes = app_state.import_context.selected_gpu_indexes()
    energy_metrics = await app_state.energy.get_energy_metrics(hours, gpu_indexes=gpu_indexes)
    carbon = await app_state.energy.get_carbon_data(hours, gpu_indexes=gpu_indexes)
    fairness = await app_state.governance.get_fairness_report(gpu_indexes=gpu_indexes)
    summary = await app_state.store.get_power_summary(hours, gpu_indexes=gpu_indexes)
    alerts = await app_state.store.get_alerts(limit=10, gpu_indexes=gpu_indexes)
```

This step intentionally scopes both row-level history (`gpu_history`, `alerts`, `process_history`) and scope-level artifacts (`schedule_log`, `optimization_snapshots`) so exported analytics cannot leak GPUs that were not part of the imported console.

- [ ] **Step 4: Run the historical-scope tests**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_import_history_scope -v"
```

Expected:

- PASS for all tests in `tests.test_import_history_scope`

- [ ] **Step 5: Commit imported-GPU history scoping**

```bash
git add backend/app/services/data_store.py backend/app/services/energy_analytics.py backend/app/services/governance.py backend/app/api/monitor.py backend/app/api/alerts.py backend/app/api/energy.py backend/app/api/governance.py tests/test_import_history_scope.py
git commit -m "feat: scope history and analytics to imported GPUs"
```

---

### Task 5: Lock Frontend Routing Split And Console Boundary With Red Tests

**Files:**
- Create: `tests/test_import_layer_structure.py`
- Create: `frontend/src/lib/importContext.test.js`
- Test: `tests/test_import_layer_structure.py`
- Test: `frontend/src/lib/importContext.test.js`

- [ ] **Step 1: Add failing frontend structure tests for the new `/import` route and console cleanup**

Create `tests/test_import_layer_structure.py` with the following content:

```python
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ImportLayerStructureTests(unittest.TestCase):
    def test_main_router_exposes_import_route(self):
        text = (ROOT / "frontend/src/main.js").read_text(encoding="utf-8")

        self.assertIn("{ path: '/import', name: 'ImportWorkspace', component: loadImportWorkspaceView }", text)

    def test_app_shell_gates_on_import_context_not_agent_connection(self):
        text = (ROOT / "frontend/src/App.vue").read_text(encoding="utf-8")

        self.assertIn("getImportContext", text)
        self.assertIn("store.setImportContext", text)
        self.assertIn("hasValidImportContext", text)
        self.assertIn("router.replace('/import')", text)
        self.assertNotIn("setWorkspaceReady(Boolean(data?.agent_connected))", text)

    def test_dashboard_no_longer_hosts_connection_center(self):
        text = (ROOT / "frontend/src/views/Dashboard.vue").read_text(encoding="utf-8")

        self.assertNotIn("接入与自检", text)
        self.assertNotIn("connection-card", text)
        self.assertNotIn("saveConnection", text)
        self.assertIn("重新导入管理卡", text)

    def test_import_workspace_and_components_exist(self):
        for rel in [
            "frontend/src/views/ImportWorkspace.vue",
            "frontend/src/components/import/ImportSourcePanel.vue",
            "frontend/src/components/import/ImportHardwareSummary.vue",
            "frontend/src/components/import/ImportGpuGrid.vue",
            "frontend/src/lib/importContext.js",
        ]:
            self.assertTrue((ROOT / rel).exists(), rel)


if __name__ == "__main__":
    unittest.main()
```

Create `frontend/src/lib/importContext.test.js`:

```js
import test from 'node:test'
import assert from 'node:assert/strict'
import { formatImportedGpuLabel, hasValidImportContext } from './importContext.js'

test('hasValidImportContext requires valid flag and imported gpu indexes', () => {
  assert.equal(hasValidImportContext(null), false)
  assert.equal(hasValidImportContext({ valid: false, imported_gpu_indexes: [0] }), false)
  assert.equal(hasValidImportContext({ valid: true, imported_gpu_indexes: [] }), false)
  assert.equal(hasValidImportContext({ valid: true, imported_gpu_indexes: [0, 2] }), true)
})

test('formatImportedGpuLabel joins selected indexes in ascending order', () => {
  assert.equal(
    formatImportedGpuLabel({ imported_gpu_indexes: [2, 0, 1] }),
    'GPU 0 / GPU 1 / GPU 2',
  )
})
```

- [ ] **Step 2: Run the tests to verify the frontend route and import UI are still missing**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_import_layer_structure -v"
cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm test -- src/lib/importContext.test.js"
```

Expected:

- Python structure tests FAIL because `/import` route and new import files do not exist yet
- `node:test` FAILS because `frontend/src/lib/importContext.js` does not exist yet

- [ ] **Step 3: Commit the red frontend tests**

```bash
git add tests/test_import_layer_structure.py frontend/src/lib/importContext.test.js
git commit -m "test: add import layer frontend coverage"
```

---

### Task 6: Implement The Import Page, App Gating, And Dashboard Cleanup

**Files:**
- Create: `frontend/src/views/ImportWorkspace.vue`
- Create: `frontend/src/components/import/ImportSourcePanel.vue`
- Create: `frontend/src/components/import/ImportHardwareSummary.vue`
- Create: `frontend/src/components/import/ImportGpuGrid.vue`
- Create: `frontend/src/lib/importContext.js`
- Modify: `frontend/src/main.js`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/services/api.js`
- Modify: `frontend/src/stores/app.js`
- Modify: `frontend/src/views/Dashboard.vue`
- Modify: `frontend/src/composables/useDashboardData.js`
- Modify: `frontend/src/components/app/AppPrimarySidebar.vue`
- Modify: `tests/test_frontend_ui_structure.py`
- Test: `tests/test_import_layer_structure.py`
- Test: `frontend/src/lib/importContext.test.js`
- Test: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Add pure import-context helpers and API bindings**

Create `frontend/src/lib/importContext.js`:

```js
export function hasValidImportContext(payload) {
  return Boolean(
    payload
    && payload.valid
    && Array.isArray(payload.imported_gpu_indexes)
    && payload.imported_gpu_indexes.length > 0,
  )
}

export function normalizeImportedGpuIndexes(indexes) {
  return Array.from(new Set((indexes || []).map((item) => Number(item))))
    .filter((item) => Number.isInteger(item) && item >= 0)
    .sort((left, right) => left - right)
}

export function formatImportedGpuLabel(payload) {
  const indexes = normalizeImportedGpuIndexes(payload?.imported_gpu_indexes || [])
  if (!indexes.length) {
    return '尚未导入 GPU'
  }
  return indexes.map((item) => `GPU ${item}`).join(' / ')
}
```

Update `frontend/src/services/api.js`:

```js
export const getImportContext = () => api.get('/system/import-context')
export const scanImportContext = (payload) => api.post('/system/import-context/scan', payload)
export const commitImportContext = (payload) => api.post('/system/import-context', payload)
export const resetImportContext = () => api.delete('/system/import-context')
```

Update `frontend/src/stores/app.js`:

```js
import { ref, computed } from 'vue'
import { hasValidImportContext } from '../lib/importContext.js'

  const importContext = ref(null)
  const workspaceReady = computed(() => hasValidImportContext(importContext.value))

  function setImportContext(value) {
    importContext.value = value || null
  }

  function applyRealtimePayload(data) {
    if (data.import_context) {
      importContext.value = data.import_context
    }
    if (data.gpus) gpus.value = data.gpus
    if (data.system) system.value = data.system
    if (data.processes) processes.value = data.processes
    if (data.alerts?.length) {
      alerts.value = [...data.alerts, ...alerts.value].slice(0, ALERT_LIMIT)
    }
  }

  return {
    gpus, system, processes, alerts, wsConnected, workspaceReady, importContext,
    dataSourceStatus, dataSourceLabel, domains,
    schedulerAuto, timePeriod,
    totalPower, avgTemperature, totalMemoryUsed, totalMemoryTotal, avgUtilization,
    normalizedProcesses, dashboardSummary, taskSummary,
    beginDomainRequest, completeDomainRequest, failDomainRequest,
    replaceProcesses,
    applyRealtimePayload,
    updateFromWs,
    setImportContext,
  }
```

- [ ] **Step 2: Add the `/import` route and build the import page UI**

Update `frontend/src/main.js`:

```js
const loadImportWorkspaceView = () => import('./views/ImportWorkspace.vue')

const routes = [
  { path: '/import', name: 'ImportWorkspace', component: loadImportWorkspaceView },
  { path: '/', name: 'Dashboard', component: loadDashboardView },
  { path: '/gpu/:index', name: 'GpuDetail', component: loadGpuDetailView },
  { path: '/tasks', name: 'TaskManager', component: loadTaskManagerView },
  { path: '/scheduler', name: 'Scheduler', component: loadSchedulerView },
  { path: '/energy', name: 'EnergyOptimization', component: loadEnergyOptimizationView },
  { path: '/ai', name: 'AIAssistant', component: loadAIAssistantView },
  { path: '/alerts', name: 'AlertCenter', component: loadAlertCenterView },
  { path: '/monitor', name: 'MonitorCenter', component: loadMonitorCenterView },
]

const heavyViewLoaders = [
  loadGpuDetailView,
  loadEnergyOptimizationView,
  loadMonitorCenterView,
  loadImportWorkspaceView,
]
```

Create `frontend/src/components/import/ImportSourcePanel.vue`:

```vue
<script setup>
const props = defineProps({
  form: { type: Object, required: true },
  busy: { type: Boolean, required: true },
  feedback: { type: Object, default: null },
})

const emit = defineEmits(['update:mode', 'update:url', 'scan'])
</script>

<template>
  <section class="tech-card import-source-panel">
    <div class="import-source-panel__head">
      <h3>选择导入来源</h3>
      <p>先确定本次要接管的是本机还是远程机器，再扫描可导入的 GPU。</p>
    </div>
    <div class="connection-toggle">
      <button class="connection-toggle__item" :class="{ 'connection-toggle__item--active': props.form.mode === 'local' }" @click="emit('update:mode', 'local')">本机</button>
      <button class="connection-toggle__item" :class="{ 'connection-toggle__item--active': props.form.mode === 'remote' }" @click="emit('update:mode', 'remote')">远程</button>
    </div>
    <input
      class="connection-input"
      :disabled="props.form.mode === 'local'"
      :value="props.form.agent_url"
      :placeholder="props.form.mode === 'local' ? 'http://127.0.0.1:8001' : 'http://192.168.1.20:8001'"
      @input="emit('update:url', $event.target.value)"
    />
    <button class="btn-tech btn-tech--primary" :disabled="props.busy" @click="emit('scan')">
      {{ props.busy ? '扫描中...' : '扫描设备' }}
    </button>
    <div v-if="props.feedback" class="action-feedback" :class="`action-feedback--${props.feedback.tone}`">
      <div class="action-feedback__title">{{ props.feedback.title }}</div>
      <div class="action-feedback__desc">{{ props.feedback.detail }}</div>
    </div>
  </section>
</template>
```

Create `frontend/src/components/import/ImportHardwareSummary.vue`:

```vue
<script setup>
const props = defineProps({
  scanResult: { type: Object, default: null },
})
</script>

<template>
  <section class="tech-card import-hardware-summary">
    <h3>设备摘要</h3>
    <div v-if="props.scanResult?.system" class="connection-facts">
      <div class="connection-facts__item">
        <span class="connection-facts__label">CPU</span>
        <span class="connection-facts__value">{{ props.scanResult.system.cpu_count || '-' }} 核</span>
      </div>
      <div class="connection-facts__item">
        <span class="connection-facts__label">CPU 当前占用</span>
        <span class="connection-facts__value">{{ Number(props.scanResult.system.cpu_percent || 0).toFixed(1) }}%</span>
      </div>
      <div class="connection-facts__item">
        <span class="connection-facts__label">扫描到 GPU</span>
        <span class="connection-facts__value">{{ (props.scanResult.gpus || []).length }} 张</span>
      </div>
    </div>
    <p v-else class="workspace-summary__empty">扫描完成后，这里会显示 CPU 与整机资源摘要。</p>
  </section>
</template>
```

Create `frontend/src/components/import/ImportGpuGrid.vue`:

```vue
<script setup>
import { computed } from 'vue'

const props = defineProps({
  gpus: { type: Array, default: () => [] },
  modelValue: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue'])

const selected = computed(() => new Set(props.modelValue))

function toggleGpu(index) {
  const next = new Set(props.modelValue)
  if (next.has(index)) {
    next.delete(index)
  } else {
    next.add(index)
  }
  emit('update:modelValue', Array.from(next).sort((left, right) => left - right))
}
</script>

<template>
  <section class="tech-card import-gpu-grid">
    <h3>选择要导入的 GPU</h3>
    <div class="cards">
      <button
        v-for="gpu in props.gpus"
        :key="gpu.index"
        type="button"
        class="card import-gpu-card"
        :class="{ 'import-gpu-card--selected': selected.has(gpu.index) }"
        @click="toggleGpu(gpu.index)"
      >
        <div class="card-body">
          <h3>GPU {{ gpu.index }} · {{ gpu.name }}</h3>
          <p>温度 {{ gpu.temperature }}°C · 功耗 {{ gpu.power_usage }}W / {{ gpu.power_limit }}W</p>
          <p>利用率 {{ gpu.gpu_utilization }}% · 显存 {{ gpu.memory_used }} / {{ gpu.memory_total }}</p>
        </div>
      </button>
    </div>
  </section>
</template>
```

Create `frontend/src/views/ImportWorkspace.vue`:

```vue
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { commitImportContext, getImportContext, scanImportContext } from '../services/api.js'
import { useAppStore } from '../stores/app.js'
import { formatImportedGpuLabel, hasValidImportContext } from '../lib/importContext.js'
import ImportSourcePanel from '../components/import/ImportSourcePanel.vue'
import ImportHardwareSummary from '../components/import/ImportHardwareSummary.vue'
import ImportGpuGrid from '../components/import/ImportGpuGrid.vue'

const router = useRouter()
const store = useAppStore()
const busy = ref(false)
const importBusy = ref(false)
const feedback = ref(null)
const scanResult = ref(null)
const selectedGpuIndexes = ref([])
const form = ref({
  mode: 'local',
  agent_url: '',
  agent_label: '',
})

const importedLabel = computed(() => formatImportedGpuLabel(store.importContext))

async function loadExistingContext() {
  const { data } = await getImportContext()
  store.setImportContext(data)
  if (hasValidImportContext(data)) {
    form.value.mode = data.source_mode || 'local'
    form.value.agent_url = data.source_mode === 'remote' ? (data.agent_url || '') : ''
    form.value.agent_label = data.agent_label || ''
  }
}

async function scanDevices() {
  busy.value = true
  feedback.value = null
  try {
    const { data } = await scanImportContext(form.value)
    scanResult.value = data
    selectedGpuIndexes.value = []
    feedback.value = data.success
      ? { tone: 'success', title: '扫描成功', detail: `发现 ${(data.gpus || []).length} 张可选 GPU。` }
      : { tone: 'warning', title: '扫描失败', detail: data.message || '无法连接到目标 Agent。' }
  } finally {
    busy.value = false
  }
}

async function submitImport() {
  importBusy.value = true
  feedback.value = null
  try {
    const { data } = await commitImportContext({
      ...form.value,
      gpu_indexes: selectedGpuIndexes.value,
    })
    store.setImportContext(data.import_context)
    router.replace('/')
  } finally {
    importBusy.value = false
  }
}

onMounted(() => {
  void loadExistingContext()
})
</script>

<template>
  <div class="workspace-page import-workspace">
    <section class="workspace-summary">
      <div class="workspace-summary__header">
        <div>
          <h2>导入管理卡</h2>
          <p>在进入控制台前，先扫描机器并选定本次要纳入治理的 GPU。</p>
        </div>
        <div class="workspace-summary__meta">
          <span class="status-badge status-badge--ok">{{ importedLabel }}</span>
        </div>
      </div>
    </section>

    <div class="overview-layout">
      <ImportSourcePanel
        :form="form"
        :busy="busy"
        :feedback="feedback"
        @update:mode="(value) => { form.mode = value; if (value === 'local') form.agent_url = '' }"
        @update:url="(value) => { form.agent_url = value }"
        @scan="scanDevices"
      />
      <ImportHardwareSummary :scan-result="scanResult" />
    </div>

    <ImportGpuGrid v-model="selectedGpuIndexes" :gpus="scanResult?.gpus || []" />

    <div class="import-workspace__actions">
      <button class="btn-tech btn-tech--primary" :disabled="importBusy || !selectedGpuIndexes.length" @click="submitImport">
        {{ importBusy ? '导入中...' : '导入并进入控制台' }}
      </button>
    </div>
  </div>
</template>
```

- [ ] **Step 3: Switch app gating to import readiness and clean `Dashboard.vue` into a pure console homepage**

Update `frontend/src/App.vue` imports:

```vue
import { getImportContext, healthCheck } from './services/api'
import { formatImportedGpuLabel, hasValidImportContext } from './lib/importContext.js'
```

Replace the old workspace status refresh logic with import-context gating:

```vue
async function refreshWorkspaceStatus() {
  try {
    const [{ data: health }, { data: importContext }] = await Promise.all([
      healthCheck(),
      getImportContext(),
    ])
    store.setImportContext(importContext)
    applyConnectionSummary(health?.connection)
    appInfo.value = {
      ...appInfo.value,
      agentSourceLabel: hasValidImportContext(importContext)
        ? `${health?.connection?.mode_label || '导入目标'} · ${formatImportedGpuLabel(importContext)}`
        : '尚未导入管理卡',
    }
  } catch {
    store.setImportContext(null)
  } finally {
    workspaceStatusChecked.value = true
    if (!store.workspaceReady && route.path !== '/import') {
      router.replace('/import')
    } else if (store.workspaceReady && route.path === '/import') {
      router.replace('/')
    }
    void syncAppInfo()
  }
}

function enforceRouteAccess(path = route.path) {
  if (path === '/import') {
    return
  }
  if (!workspaceLocked.value) {
    return
  }
  router.replace('/import')
  setLockHint('当前还未导入管理卡，已返回导入层。')
}

function navigateTo(item) {
  if (workspaceLocked.value && item.path !== '/import') {
    setLockHint(`请先完成 GPU 导入，再进入“${item.label}”页面。`)
    router.replace('/import')
    return
  }
  if (route.path !== item.path) {
    router.push(item.path)
  }
}
```

Update `frontend/src/composables/useDashboardData.js` so dashboard no longer owns connection refresh:

```js
import {
  getFairnessGovernance,
  getSchedulerStatus,
  getSystemSelfCheck,
  healthCheck,
} from '../services/api.js'

  return {
    dashboardSummary: computed(() => store.dashboardSummary),
    governanceDomain: computed(() => store.domains.dashboard.governance),
    refreshGovernance: governanceRefresh.refresh,
  }
```

Update `frontend/src/views/Dashboard.vue`:

```vue
const dashboardTabs = [
  { key: 'overview', label: '概览', desc: '判断与入口' },
  { key: 'live', label: '实时态势', desc: 'GPU、图表、告警' },
]
```

Remove:

- `connectionState`
- `connectionForm`
- `connectionBusy`
- `connectionDirty`
- `connectionFeedback`
- `remoteAssistState`
- `refreshConnection`
- the entire “接入与自检” tab block

Add a single header action:

```vue
<button class="btn-tech" @click="router.push('/import')">重新导入管理卡</button>
```

Update `frontend/src/components/app/AppPrimarySidebar.vue` copy:

```vue
        <p class="app-primary-sidebar__sub">
          {{ props.workspaceLocked ? 'IMPORT FIRST · CONSOLE LATER' : 'LAB · OPS · IMPORTED GPU SCOPE' }}
        </p>
        <div class="app-primary-sidebar__source">
          <span class="app-primary-sidebar__source-label">连接</span>
          <strong class="app-primary-sidebar__source-value">
            {{ props.appInfo.agentSourceLabel || '按导入范围治理' }}
          </strong>
        </div>
```

Update `tests/test_frontend_ui_structure.py` by replacing the dashboard-access assumptions with:

```python
    def test_dashboard_is_console_only_and_offers_reimport_entry(self):
        text = (ROOT / "frontend/src/views/Dashboard.vue").read_text(encoding="utf-8")

        self.assertIn("重新导入管理卡", text)
        self.assertNotIn("接入与自检", text)
        self.assertNotIn("connection-card", text)
        self.assertNotIn("saveConnection", text)
```

- [ ] **Step 4: Run the frontend test suite slices and a production build**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_import_layer_structure tests.test_frontend_ui_structure -v"
cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm test -- src/lib/importContext.test.js src/stores/app.test.js"
cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm run build"
```

Expected:

- PASS for `tests.test_import_layer_structure`
- PASS for `tests.test_frontend_ui_structure`
- PASS for the targeted `node:test` files
- Vite build exits with code `0`

- [ ] **Step 5: Commit the import-layer frontend and dashboard cleanup**

```bash
git add frontend/src/main.js frontend/src/App.vue frontend/src/services/api.js frontend/src/stores/app.js frontend/src/views/ImportWorkspace.vue frontend/src/components/import/ImportSourcePanel.vue frontend/src/components/import/ImportHardwareSummary.vue frontend/src/components/import/ImportGpuGrid.vue frontend/src/lib/importContext.js frontend/src/lib/importContext.test.js frontend/src/composables/useDashboardData.js frontend/src/views/Dashboard.vue frontend/src/components/app/AppPrimarySidebar.vue tests/test_import_layer_structure.py tests/test_frontend_ui_structure.py
git commit -m "feat: add GPU import entry workflow"
```
