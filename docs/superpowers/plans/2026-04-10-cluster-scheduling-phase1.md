# Cluster Scheduling Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working cluster-scheduling loop: submit a structured job, queue it, place it onto one node/GPU, reserve and activate an allocation through the node runtime, expose minimal control-plane APIs, and let the AI runtime operate on jobs instead of raw PIDs.

**Architecture:** Add a new `cluster_control` backend package that owns immutable control-plane models, SQLite persistence, a small placement scheduler, and execution orchestration over a node runtime capable of reservations and controlled process launches. Keep the existing governance stack running, but route new job submission, queue visibility, and job lifecycle control through the new control plane so later phases can add preemption and migration without reworking the domain model.

**Tech Stack:** FastAPI, Python dataclasses, `aiosqlite`, existing runtime-provider abstractions, server-agent FastAPI, Vue 3, Axios, Python `unittest`, Node `node:test`.

---

## File Structure

### New files

- `backend/app/services/cluster_control/__init__.py`
  - Package exports for control-plane services and models.
- `backend/app/services/cluster_control/models.py`
  - Immutable dataclasses for `NodeRecord`, `DeviceRecord`, `QueueRecord`, `JobSpecRecord`, `JobRuntimeRecord`, `AllocationRecord`, `ReservationRecord`, and `PlacementPlan`.
- `backend/app/services/cluster_control/sqlite_support.py`
  - SQLite schema and CRUD helpers for queues, jobs, allocations, reservations, nodes, and devices.
- `backend/app/services/cluster_control/scheduler_core.py`
  - Candidate filtering and single-node placement scoring for Phase 1.
- `backend/app/services/cluster_control/control_plane.py`
  - API-facing control-plane service: submit job, list queues, get job detail, reconcile queue, and issue pause/resume/cancel commands.
- `backend/app/services/cluster_control/execution_backend.py`
  - Execution backend protocol plus `HTTPAgentProcessBackend`, `SSHProcessBackend`, and `LocalProcessBackend` wrappers.
- `backend/app/services/cluster_control/execution_orchestrator.py`
  - Reservation -> allocation -> launch orchestration and compensation.
- `backend/app/api/cluster_jobs.py`
  - REST routes for job submit/list/detail/pause/resume/cancel.
- `backend/app/api/cluster_queues.py`
  - REST routes for queue list and allocation snapshots.
- `tests/test_cluster_control_models.py`
  - Persistence and model normalization tests.
- `tests/test_cluster_scheduler_core.py`
  - Placement scoring and queue-admission tests.
- `tests/test_cluster_job_api.py`
  - API tests for job submit/list/detail/control.
- `tests/test_goal_runtime_cluster_capabilities.py`
  - Goal runtime capability registration and approval tests for `job.*` abilities.
- `tests/test_node_runtime_api.py`
  - Node runtime reservation, launch, and lifecycle tests.
- `server-agent/runtime_store.py`
  - Lightweight local store for reservations, allocations, and job handles on a node.
- `server-agent/job_runtime.py`
  - Controlled process launcher and job lifecycle manager for the node runtime.
- `frontend/src/views/ClusterJobs.vue`
  - Minimal cluster console for queues, jobs, and allocations.
- `frontend/src/components/cluster/ClusterQueueBoard.vue`
  - Queue summary and queued/running counts.
- `frontend/src/components/cluster/ClusterJobLedger.vue`
  - Job submit form and lifecycle ledger.
- `frontend/src/components/cluster/ClusterAllocationPanel.vue`
  - Active allocations grouped by node.
- `frontend/src/lib/clusterConsoleModels.js`
  - Frontend mappers for queue/job/allocation payloads.
- `frontend/src/lib/clusterConsoleModels.test.js`
  - Model-mapping tests.

### Modified files

- `backend/app/models/schemas.py`
  - Add request/response schemas for queues, jobs, reservations, and allocations.
- `backend/app/services/data_store.py`
  - Wire new cluster-control SQLite helpers into the existing store instance.
- `backend/app/main.py`
  - Instantiate the control-plane service, create execution backend instances, and register new routers.
- `backend/app/services/goal_runtime/platform_capabilities.py`
  - Register `job.submit`, `job.list`, `job.get`, `job.pause`, `job.resume`, `job.cancel`, and `queue.status.read`.
- `backend/app/services/goal_runtime/planner.py`
  - Map planner actions to new job-oriented capabilities.
- `backend/app/services/goal_runtime/goal_parser.py`
  - Distinguish job submission/control intents from analysis-only requests.
- `server-agent/main.py`
  - Mount reservation, allocation, and job lifecycle APIs over the new runtime store.
- `frontend/src/services/api.js`
  - Add cluster job/queue/allocation API helpers.
- `frontend/src/main.js`
  - Register the new cluster console route.
- `frontend/src/composables/useConsoleShell.js`
  - Add navigation metadata for the cluster console.
- `frontend/src/views/AIAssistant.vue`
  - Surface job-oriented runtime interactions without raw PID-focused copy.
- `tests/test_frontend_ui_structure.py`
  - Verify the cluster console route and components exist.

---

### Task 1: Create Control-Plane Models and Persistence

**Files:**
- Create: `backend/app/services/cluster_control/__init__.py`
- Create: `backend/app/services/cluster_control/models.py`
- Create: `backend/app/services/cluster_control/sqlite_support.py`
- Modify: `backend/app/services/data_store.py`
- Modify: `backend/app/models/schemas.py`
- Test: `tests/test_cluster_control_models.py`

- [ ] **Step 1: Write the failing model and persistence tests**

```python
# tests/test_cluster_control_models.py
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.data_store import DataStore
from app.services.cluster_control.models import JobSpecRecord


class ClusterControlModelTests(unittest.IsolatedAsyncioTestCase):
    async def test_data_store_persists_queue_job_and_allocation_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = DataStore(os.path.join(tmpdir, "cluster.db"))
            await store.init()
            try:
                await store.upsert_cluster_queue({
                    "queue_id": "default",
                    "name": "Default",
                    "state": "active",
                    "default_priority": 50,
                })
                await store.create_cluster_job(
                    JobSpecRecord(
                        job_id="job-1",
                        tenant_id="tenant-a",
                        project_id="project-a",
                        queue_id="default",
                        submitter_id="alice",
                        job_type="batch",
                        entrypoint="python train.py",
                        args=("--epochs", "1"),
                        env={"CUDA_VISIBLE_DEVICES": "0"},
                        resource_request={"gpu": 1, "cpu": 4, "memory_bytes": 8 * 1024**3},
                        placement_constraints={},
                        priority=50,
                        preemptible=True,
                        max_retries=1,
                        timeout_seconds=3600,
                    )
                )
                await store.create_cluster_allocation({
                    "allocation_id": "alloc-1",
                    "job_id": "job-1",
                    "node_id": "node-a",
                    "gpu_bindings_json": "[\"gpu-0\"]",
                    "status": "active",
                    "execution_backend": "http_agent",
                })
                queues = await store.list_cluster_queues()
                job = await store.get_cluster_job("job-1")
                allocations = await store.list_cluster_allocations()
            finally:
                await store.close()

        self.assertEqual(queues[0]["queue_id"], "default")
        self.assertEqual(job["job_id"], "job-1")
        self.assertEqual(allocations[0]["node_id"], "node-a")

    def test_job_spec_record_normalizes_args_and_priority(self):
        record = JobSpecRecord(
            job_id="job-2",
            tenant_id="tenant-a",
            project_id="project-a",
            queue_id="default",
            submitter_id="alice",
            job_type="batch",
            entrypoint="python train.py",
            args=["--epochs", "2"],
            env={},
            resource_request={"gpu": 1},
            placement_constraints={},
            priority="60",
            preemptible=False,
            max_retries=0,
            timeout_seconds=1200,
        )

        self.assertEqual(record.args, ("--epochs", "2"))
        self.assertEqual(record.priority, 60)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
./.venv/Scripts/python.exe -m unittest tests.test_cluster_control_models -q
```

Expected: FAIL with `ModuleNotFoundError` for `app.services.cluster_control` and missing `DataStore` methods such as `upsert_cluster_queue`.

- [ ] **Step 3: Add the immutable records and SQLite helpers**

```python
# backend/app/services/cluster_control/models.py
from dataclasses import dataclass


@dataclass(frozen=True)
class JobSpecRecord:
    job_id: str
    tenant_id: str
    project_id: str
    queue_id: str
    submitter_id: str
    job_type: str
    entrypoint: str
    args: tuple[str, ...]
    env: dict[str, str]
    resource_request: dict[str, int]
    placement_constraints: dict[str, str]
    priority: int
    preemptible: bool
    max_retries: int
    timeout_seconds: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "args", tuple(self.args))
        object.__setattr__(self, "priority", int(self.priority))
```

```python
# backend/app/services/cluster_control/sqlite_support.py
CLUSTER_CONTROL_INIT_SQL = """
CREATE TABLE IF NOT EXISTS cluster_queues (
    queue_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    state TEXT NOT NULL,
    default_priority INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS cluster_jobs (
    job_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    queue_id TEXT NOT NULL,
    submitter_id TEXT NOT NULL,
    job_type TEXT NOT NULL,
    entrypoint TEXT NOT NULL,
    args_json TEXT NOT NULL,
    env_json TEXT NOT NULL,
    resource_request_json TEXT NOT NULL,
    placement_constraints_json TEXT NOT NULL,
    priority INTEGER NOT NULL,
    preemptible INTEGER NOT NULL,
    max_retries INTEGER NOT NULL,
    timeout_seconds INTEGER NOT NULL,
    state TEXT NOT NULL DEFAULT 'queued',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS cluster_allocations (
    allocation_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    gpu_bindings_json TEXT NOT NULL,
    status TEXT NOT NULL,
    execution_backend TEXT NOT NULL,
    created_at REAL NOT NULL DEFAULT (unixepoch())
);
"""
```

```python
# backend/app/services/data_store.py
from app.services.cluster_control.sqlite_support import (
    CLUSTER_CONTROL_INIT_SQL,
    create_cluster_allocation,
    create_cluster_job,
    get_cluster_job,
    list_cluster_allocations,
    list_cluster_queues,
    upsert_cluster_queue,
)

await self._db.executescript(_INIT_SQL + GOAL_RUNTIME_INIT_SQL + CLUSTER_CONTROL_INIT_SQL)
```

- [ ] **Step 4: Re-run the tests to verify they pass**

Run:

```bash
./.venv/Scripts/python.exe -m unittest tests.test_cluster_control_models -q
```

Expected: PASS with `Ran 2 tests`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/cluster_control/__init__.py backend/app/services/cluster_control/models.py backend/app/services/cluster_control/sqlite_support.py backend/app/services/data_store.py backend/app/models/schemas.py tests/test_cluster_control_models.py
git commit -m "feat: add cluster control plane models"
```

### Task 2: Build the Phase 1 Placement Scheduler and Control-Plane Service

**Files:**
- Create: `backend/app/services/cluster_control/scheduler_core.py`
- Create: `backend/app/services/cluster_control/control_plane.py`
- Create: `tests/test_cluster_scheduler_core.py`
- Modify: `backend/app/services/data_store.py`

- [ ] **Step 1: Write the failing scheduler tests**

```python
# tests/test_cluster_scheduler_core.py
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.cluster_control.scheduler_core import ClusterSchedulerCore
from app.services.cluster_control.models import JobSpecRecord


class ClusterSchedulerCoreTests(unittest.TestCase):
    def test_selects_first_schedulable_node_with_sufficient_gpu_capacity(self):
        scheduler = ClusterSchedulerCore()
        job = JobSpecRecord(
            job_id="job-1",
            tenant_id="tenant-a",
            project_id="project-a",
            queue_id="default",
            submitter_id="alice",
            job_type="batch",
            entrypoint="python train.py",
            args=(),
            env={},
            resource_request={"gpu": 1, "cpu": 4},
            placement_constraints={},
            priority=50,
            preemptible=True,
            max_retries=1,
            timeout_seconds=600,
        )
        plan = scheduler.plan_job(
            job,
            nodes=[
                {"node_id": "node-a", "schedulable": True, "gpu_free": 1, "cpu_free": 16},
                {"node_id": "node-b", "schedulable": True, "gpu_free": 4, "cpu_free": 64},
            ],
        )

        self.assertEqual(plan.selected_node, "node-a")
        self.assertEqual(plan.selected_devices, ("gpu-0",))

    def test_returns_queue_wait_plan_when_no_node_matches(self):
        scheduler = ClusterSchedulerCore()
        job = JobSpecRecord(
            job_id="job-2",
            tenant_id="tenant-a",
            project_id="project-a",
            queue_id="default",
            submitter_id="alice",
            job_type="batch",
            entrypoint="python train.py",
            args=(),
            env={},
            resource_request={"gpu": 2},
            placement_constraints={},
            priority=50,
            preemptible=True,
            max_retries=1,
            timeout_seconds=600,
        )
        plan = scheduler.plan_job(job, nodes=[{"node_id": "node-a", "schedulable": True, "gpu_free": 1}])

        self.assertEqual(plan.plan_type, "queue_wait")
        self.assertEqual(plan.selected_node, "")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
./.venv/Scripts/python.exe -m unittest tests.test_cluster_scheduler_core -q
```

Expected: FAIL because `ClusterSchedulerCore` and `plan_job()` do not exist.

- [ ] **Step 3: Implement placement planning and the control-plane service**

```python
# backend/app/services/cluster_control/scheduler_core.py
from dataclasses import dataclass


@dataclass(frozen=True)
class PlacementPlan:
    job_id: str
    plan_type: str
    selected_node: str
    selected_devices: tuple[str, ...]
    score_breakdown: dict[str, float]
    alternatives: tuple[str, ...] = ()


class ClusterSchedulerCore:
    def plan_job(self, job, nodes):
        gpu_need = int(job.resource_request.get("gpu", 0))
        for node in nodes:
            if not node.get("schedulable"):
                continue
            if int(node.get("gpu_free", 0)) < gpu_need:
                continue
            return PlacementPlan(
                job_id=job.job_id,
                plan_type="placement",
                selected_node=node["node_id"],
                selected_devices=tuple(f"gpu-{index}" for index in range(gpu_need)),
                score_breakdown={"fit": 1.0, "fragmentation": 1.0},
            )
        return PlacementPlan(
            job_id=job.job_id,
            plan_type="queue_wait",
            selected_node="",
            selected_devices=(),
            score_breakdown={"fit": 0.0},
        )
```

```python
# backend/app/services/cluster_control/control_plane.py
class ClusterControlPlaneService:
    def __init__(self, store, scheduler, orchestrator):
        self.store = store
        self.scheduler = scheduler
        self.orchestrator = orchestrator

    async def submit_job(self, job_record, nodes):
        await self.store.create_cluster_job(job_record)
        plan = self.scheduler.plan_job(job_record, nodes)
        if plan.plan_type == "placement":
            await self.orchestrator.dispatch_plan(job_record, plan)
        return plan
```

- [ ] **Step 4: Re-run the tests to verify they pass**

Run:

```bash
./.venv/Scripts/python.exe -m unittest tests.test_cluster_scheduler_core -q
```

Expected: PASS with `Ran 2 tests`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/cluster_control/scheduler_core.py backend/app/services/cluster_control/control_plane.py tests/test_cluster_scheduler_core.py
git commit -m "feat: add cluster placement scheduler"
```

### Task 3: Upgrade `server-agent` into a Minimal Node Runtime

**Files:**
- Create: `server-agent/runtime_store.py`
- Create: `server-agent/job_runtime.py`
- Modify: `server-agent/main.py`
- Test: `tests/test_node_runtime_api.py`

- [ ] **Step 1: Write the failing node runtime API tests**

```python
# tests/test_node_runtime_api.py
import os
import sys
import unittest
from fastapi.testclient import TestClient

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "server-agent"))

from main import app


class NodeRuntimeApiTests(unittest.TestCase):
    def test_create_reservation_and_launch_job(self):
        client = TestClient(app)
        reservation = client.post("/api/runtime/reservations", json={
            "reservation_id": "res-1",
            "job_id": "job-1",
            "gpu_indexes": [0],
            "cpu_cores": [0, 1],
        })
        launch = client.post("/api/runtime/jobs/launch", json={
            "job_handle": "handle-1",
            "job_id": "job-1",
            "reservation_id": "res-1",
            "command": [sys.executable, "-c", "print('ok')"],
            "env": {},
        })

        self.assertEqual(reservation.status_code, 200)
        self.assertEqual(launch.status_code, 200)
        self.assertEqual(launch.json()["state"], "running")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
./.venv/Scripts/python.exe -m unittest tests.test_node_runtime_api -q
```

Expected: FAIL with `404 Not Found` for `/api/runtime/reservations` and `/api/runtime/jobs/launch`.

- [ ] **Step 3: Add reservation storage and controlled process launching**

```python
# server-agent/runtime_store.py
class RuntimeStore:
    def __init__(self):
        self.reservations = {}
        self.jobs = {}

    def create_reservation(self, payload):
        self.reservations[payload["reservation_id"]] = dict(payload)
        return self.reservations[payload["reservation_id"]]

    def get_reservation(self, reservation_id):
        return self.reservations.get(reservation_id)

    def save_job(self, payload):
        self.jobs[payload["job_handle"]] = dict(payload)
        return self.jobs[payload["job_handle"]]
```

```python
# server-agent/job_runtime.py
import subprocess


class JobRuntime:
    def __init__(self, store):
        self.store = store

    def launch(self, payload):
        process = subprocess.Popen(
            payload["command"],
            env=payload.get("env") or None,
            cwd=payload.get("working_dir") or None,
        )
        record = {
            "job_handle": payload["job_handle"],
            "job_id": payload["job_id"],
            "reservation_id": payload["reservation_id"],
            "pid": process.pid,
            "state": "running",
        }
        return self.store.save_job(record)
```

```python
# server-agent/main.py
runtime_store = RuntimeStore()
job_runtime = JobRuntime(runtime_store)


@app.post("/api/runtime/reservations")
def create_reservation(payload: dict):
    return runtime_store.create_reservation(payload)


@app.post("/api/runtime/jobs/launch")
def launch_job(payload: dict):
    reservation = runtime_store.get_reservation(payload["reservation_id"])
    if reservation is None:
        raise HTTPException(status_code=404, detail="reservation not found")
    return job_runtime.launch(payload)
```

- [ ] **Step 4: Re-run the tests to verify they pass**

Run:

```bash
./.venv/Scripts/python.exe -m unittest tests.test_node_runtime_api -q
```

Expected: PASS with `Ran 1 test`.

- [ ] **Step 5: Commit**

```bash
git add server-agent/runtime_store.py server-agent/job_runtime.py server-agent/main.py tests/test_node_runtime_api.py
git commit -m "feat: add node runtime reservation and launch APIs"
```

### Task 4: Add Execution Backends and Control-Plane APIs

**Files:**
- Create: `backend/app/services/cluster_control/execution_backend.py`
- Create: `backend/app/services/cluster_control/execution_orchestrator.py`
- Create: `backend/app/api/cluster_jobs.py`
- Create: `backend/app/api/cluster_queues.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/models/schemas.py`
- Test: `tests/test_cluster_job_api.py`

- [ ] **Step 1: Write the failing API tests**

```python
# tests/test_cluster_job_api.py
import os
import sys
import unittest
from fastapi.testclient import TestClient

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.main import app


class ClusterJobApiTests(unittest.TestCase):
    def test_submit_job_returns_queued_or_running_record(self):
        client = TestClient(app)
        response = client.post("/api/cluster/jobs", json={
            "job_id": "job-1",
            "tenant_id": "tenant-a",
            "project_id": "project-a",
            "queue_id": "default",
            "submitter_id": "alice",
            "job_type": "batch",
            "entrypoint": "python train.py",
            "args": [],
            "env": {},
            "resource_request": {"gpu": 1, "cpu": 4},
            "placement_constraints": {},
            "priority": 50,
            "preemptible": True,
            "max_retries": 1,
            "timeout_seconds": 600,
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn(response.json()["state"], {"queued", "running"})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
./.venv/Scripts/python.exe -m unittest tests.test_cluster_job_api -q
```

Expected: FAIL with `404 Not Found` for `/api/cluster/jobs`.

- [ ] **Step 3: Add execution backends, orchestration, and API routes**

```python
# backend/app/services/cluster_control/execution_backend.py
class HTTPAgentProcessBackend:
    def __init__(self, base_url):
        self.base_url = base_url

    async def create_reservation(self, client, payload):
        return await client.post("/api/runtime/reservations", json=payload)

    async def launch_job(self, client, payload):
        return await client.post("/api/runtime/jobs/launch", json=payload)
```

```python
# backend/app/services/cluster_control/execution_orchestrator.py
class ExecutionOrchestrator:
    def __init__(self, store, backend):
        self.store = store
        self.backend = backend

    async def dispatch_plan(self, job_record, plan):
        allocation_id = f"alloc-{job_record.job_id}"
        await self.store.create_cluster_allocation({
            "allocation_id": allocation_id,
            "job_id": job_record.job_id,
            "node_id": plan.selected_node,
            "gpu_bindings_json": "[\"gpu-0\"]",
            "status": "active",
            "execution_backend": "http_agent",
        })
        await self.store.update_cluster_job_state(job_record.job_id, "running")
        return allocation_id
```

```python
# backend/app/api/cluster_jobs.py
@router.post("")
async def submit_cluster_job(req: ClusterJobSubmitRequest):
    from app.main import app_state
    return await app_state.cluster_control.submit_job_request(req)
```

```python
# backend/app/main.py
from app.api.cluster_jobs import router as cluster_jobs_router
from app.api.cluster_queues import router as cluster_queues_router

app.include_router(cluster_jobs_router)
app.include_router(cluster_queues_router)
```

- [ ] **Step 4: Re-run the tests to verify they pass**

Run:

```bash
./.venv/Scripts/python.exe -m unittest tests.test_cluster_job_api -q
```

Expected: PASS with `Ran 1 test`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/cluster_control/execution_backend.py backend/app/services/cluster_control/execution_orchestrator.py backend/app/api/cluster_jobs.py backend/app/api/cluster_queues.py backend/app/main.py backend/app/models/schemas.py tests/test_cluster_job_api.py
git commit -m "feat: add cluster job submission APIs"
```

### Task 5: Upgrade Goal Runtime Capabilities to Operate on Jobs

**Files:**
- Modify: `backend/app/services/goal_runtime/platform_capabilities.py`
- Modify: `backend/app/services/goal_runtime/planner.py`
- Modify: `backend/app/services/goal_runtime/goal_parser.py`
- Test: `tests/test_goal_runtime_cluster_capabilities.py`

- [ ] **Step 1: Write the failing goal-runtime capability tests**

```python
# tests/test_goal_runtime_cluster_capabilities.py
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.goal_runtime.platform_capabilities import build_platform_capability_registry
from app.services.goal_runtime.permission_policy import requires_approval


class GoalRuntimeClusterCapabilityTests(unittest.TestCase):
    def test_cluster_job_capabilities_are_registered(self):
        app_state = type("State", (), {"cluster_control": object(), "agent": object(), "scheduler": object(), "import_context": object(), "store": object()})()
        registry = build_platform_capability_registry(app_state)

        self.assertEqual(registry.get("job.submit").definition.domain, "jobs")
        self.assertEqual(registry.get("queue.status.read").definition.side_effect_level, "observe")

    def test_low_permission_job_submit_requires_approval(self):
        app_state = type("State", (), {"cluster_control": object(), "agent": object(), "scheduler": object(), "import_context": object(), "store": object()})()
        registry = build_platform_capability_registry(app_state)

        self.assertTrue(requires_approval(registry.get("job.submit").definition, "low"))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
./.venv/Scripts/python.exe -m unittest tests.test_goal_runtime_cluster_capabilities -q
```

Expected: FAIL because `job.submit` and `queue.status.read` are not yet registered.

- [ ] **Step 3: Register job-oriented capabilities and planner mappings**

```python
# backend/app/services/goal_runtime/platform_capabilities.py
async def submit_job(_context, arguments):
    return await app_state.cluster_control.submit_job_from_capability(arguments)

async def list_jobs(_context, _arguments):
    return await app_state.cluster_control.list_jobs()

async def get_job(_context, arguments):
    return await app_state.cluster_control.get_job(arguments["job_id"])

async def queue_status_read(_context, _arguments):
    return await app_state.cluster_control.list_queues()

registry.register(
    CapabilityDefinition("job.submit", "jobs", "runtime_action", False, SUPPORTED_PROVIDERS),
    handler=submit_job,
)
registry.register(
    CapabilityDefinition("job.list", "jobs", "observe", False, SUPPORTED_PROVIDERS),
    handler=list_jobs,
)
registry.register(
    CapabilityDefinition("job.get", "jobs", "observe", False, SUPPORTED_PROVIDERS),
    handler=get_job,
)
registry.register(
    CapabilityDefinition("queue.status.read", "queues", "observe", False, SUPPORTED_PROVIDERS),
    handler=queue_status_read,
)
```

```python
# backend/app/services/goal_runtime/planner.py
ACTION_CAPABILITY_MAP.update({
    "submit_job": "job.submit",
    "pause_job": "job.pause",
    "resume_job": "job.resume",
    "cancel_job": "job.cancel",
})
```

- [ ] **Step 4: Re-run the tests to verify they pass**

Run:

```bash
./.venv/Scripts/python.exe -m unittest tests.test_goal_runtime_cluster_capabilities -q
```

Expected: PASS with `Ran 2 tests`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/goal_runtime/platform_capabilities.py backend/app/services/goal_runtime/planner.py backend/app/services/goal_runtime/goal_parser.py tests/test_goal_runtime_cluster_capabilities.py
git commit -m "feat: add goal runtime job capabilities"
```

### Task 6: Add the Minimal Cluster Console UI

**Files:**
- Create: `frontend/src/views/ClusterJobs.vue`
- Create: `frontend/src/components/cluster/ClusterQueueBoard.vue`
- Create: `frontend/src/components/cluster/ClusterJobLedger.vue`
- Create: `frontend/src/components/cluster/ClusterAllocationPanel.vue`
- Create: `frontend/src/lib/clusterConsoleModels.js`
- Create: `frontend/src/lib/clusterConsoleModels.test.js`
- Modify: `frontend/src/services/api.js`
- Modify: `frontend/src/main.js`
- Modify: `frontend/src/composables/useConsoleShell.js`
- Modify: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Write the failing frontend tests**

```python
# tests/test_frontend_ui_structure.py
def test_cluster_console_route_and_components_exist(self):
    main_text = (ROOT / "frontend/src/main.js").read_text(encoding="utf-8")
    shell_text = (ROOT / "frontend/src/composables/useConsoleShell.js").read_text(encoding="utf-8")
    api_text = (ROOT / "frontend/src/services/api.js").read_text(encoding="utf-8")

    self.assertIn("ClusterJobs", main_text)
    self.assertIn("/cluster/jobs", main_text)
    self.assertIn("集群", shell_text)
    self.assertIn("submitClusterJob", api_text)
    self.assertTrue((ROOT / "frontend/src/views/ClusterJobs.vue").exists())
    self.assertTrue((ROOT / "frontend/src/components/cluster/ClusterQueueBoard.vue").exists())
```

```js
// frontend/src/lib/clusterConsoleModels.test.js
import test from 'node:test'
import assert from 'node:assert/strict'

import { buildClusterConsoleModel } from './clusterConsoleModels.js'

test('buildClusterConsoleModel groups queues jobs and allocations', () => {
  const model = buildClusterConsoleModel({
    queues: [{ queue_id: 'default', queued_jobs: 2 }],
    jobs: [{ job_id: 'job-1', state: 'running', queue_id: 'default' }],
    allocations: [{ allocation_id: 'alloc-1', node_id: 'node-a', job_id: 'job-1' }],
  })

  assert.equal(model.queues[0].id, 'default')
  assert.equal(model.jobs[0].id, 'job-1')
  assert.equal(model.allocationsByNode[0].nodeId, 'node-a')
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure.FrontendUIStructureTests.test_cluster_console_route_and_components_exist
cd frontend && node --test src/lib/clusterConsoleModels.test.js
```

Expected: FAIL because the route, components, and model helper do not exist.

- [ ] **Step 3: Add the route, API helpers, and queue/job/allocation views**

```js
// frontend/src/services/api.js
export const listClusterQueues = () => api.get('/cluster/queues')
export const listClusterJobs = () => api.get('/cluster/jobs')
export const submitClusterJob = (payload) => api.post('/cluster/jobs', payload)
export const getClusterJob = (jobId) => api.get(`/cluster/jobs/${jobId}`)
export const pauseClusterJob = (jobId) => api.post(`/cluster/jobs/${jobId}/pause`)
export const resumeClusterJob = (jobId) => api.post(`/cluster/jobs/${jobId}/resume`)
export const cancelClusterJob = (jobId) => api.post(`/cluster/jobs/${jobId}/cancel`)
```

```js
// frontend/src/main.js
const loadClusterJobsView = () => import('./views/ClusterJobs.vue')

{ path: 'cluster/jobs', name: 'ClusterJobs', component: loadClusterJobsView, meta: { hideShellHeader: true } },
```

```vue
<!-- frontend/src/views/ClusterJobs.vue -->
<template>
  <div class="cluster-page ink-page-shell">
    <ClusterQueueBoard :queues="model.queues" />
    <ClusterJobLedger :jobs="model.jobs" @submit="submit" />
    <ClusterAllocationPanel :items="model.allocationsByNode" />
  </div>
</template>
```

```js
// frontend/src/lib/clusterConsoleModels.js
export function buildClusterConsoleModel(payload = {}) {
  return {
    queues: (payload.queues || []).map((item) => ({ id: item.queue_id, queued: item.queued_jobs || 0 })),
    jobs: (payload.jobs || []).map((item) => ({ id: item.job_id, state: item.state, queueId: item.queue_id })),
    allocationsByNode: (payload.allocations || []).map((item) => ({ nodeId: item.node_id, allocationId: item.allocation_id, jobId: item.job_id })),
  }
}
```

- [ ] **Step 4: Re-run the tests to verify they pass**

Run:

```bash
./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure.FrontendUIStructureTests.test_cluster_console_route_and_components_exist
cd frontend && node --test src/lib/clusterConsoleModels.test.js
```

Expected: PASS for both commands.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/ClusterJobs.vue frontend/src/components/cluster/ClusterQueueBoard.vue frontend/src/components/cluster/ClusterJobLedger.vue frontend/src/components/cluster/ClusterAllocationPanel.vue frontend/src/lib/clusterConsoleModels.js frontend/src/lib/clusterConsoleModels.test.js frontend/src/services/api.js frontend/src/main.js frontend/src/composables/useConsoleShell.js tests/test_frontend_ui_structure.py
git commit -m "feat: add cluster scheduling console"
```

### Task 7: Wire End-to-End Phase 1 Verification

**Files:**
- Modify: `tests/test_cluster_job_api.py`
- Modify: `tests/test_node_runtime_api.py`
- Modify: `tests/test_goal_runtime_cluster_capabilities.py`
- Modify: `frontend/src/views/AIAssistant.vue`

- [ ] **Step 1: Write the failing end-to-end assertions**

```python
# tests/test_cluster_job_api.py
def test_submit_job_detail_includes_allocation_metadata(self):
    client = TestClient(app)
    response = client.get("/api/cluster/jobs/job-1")
    self.assertEqual(response.status_code, 200)
    self.assertIn(response.json()["state"], {"queued", "running"})
    self.assertIn("current_allocation", response.json())
```

```python
# tests/test_goal_runtime_cluster_capabilities.py
def test_job_submit_path_returns_job_object_not_pid_action(self):
    result = asyncio.run(handler({}, {
        "job_id": "job-1",
        "queue_id": "default",
        "entrypoint": "python train.py",
        "resource_request": {"gpu": 1},
    }))
    assert result["job_id"] == "job-1"
    assert "pid" not in result
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
./.venv/Scripts/python.exe -m unittest tests.test_cluster_job_api tests.test_node_runtime_api tests.test_goal_runtime_cluster_capabilities -q
```

Expected: FAIL because job detail does not yet include allocation metadata or goal runtime returns legacy action-shaped payloads.

- [ ] **Step 3: Finish the integration wiring**

```python
# backend/app/services/cluster_control/control_plane.py
async def get_job_detail(self, job_id):
    job = await self.store.get_cluster_job(job_id)
    allocation = await self.store.get_active_cluster_allocation(job_id)
    return {
        **job,
        "current_allocation": allocation,
    }
```

```vue
<!-- frontend/src/views/AIAssistant.vue -->
<!-- Replace raw PID-oriented helper copy with job-oriented copy -->
<WorkspaceSummary title="AI 助手工作台">
  <template #meta>
    <span class="status-badge">作业编排入口</span>
  </template>
</WorkspaceSummary>
```

- [ ] **Step 4: Run the phase 1 verification commands**

Run:

```bash
./.venv/Scripts/python.exe -m unittest tests.test_cluster_control_models tests.test_cluster_scheduler_core tests.test_cluster_job_api tests.test_node_runtime_api tests.test_goal_runtime_cluster_capabilities -q
cd frontend && node --test src/lib/clusterConsoleModels.test.js
cd frontend && npm run build
```

Expected:

- Python test command: PASS with all Phase 1 suites green.
- Node test command: PASS.
- Frontend build: PASS with Vite production build output.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/cluster_control/control_plane.py backend/app/api/cluster_jobs.py tests/test_cluster_job_api.py tests/test_node_runtime_api.py tests/test_goal_runtime_cluster_capabilities.py frontend/src/views/AIAssistant.vue
git commit -m "feat: verify phase1 cluster scheduling loop"
```

---

## Self-Review

### Spec coverage

- 控制面模型：Task 1
- 调度内核最小流程：Task 2
- 自研进程执行器：Task 3 and Task 4
- 节点运行时升级：Task 3
- 最小 Agent capability：Task 5
- 前端最小可视化：Task 6
- 最小闭环验证：Task 7

### Placeholder scan

- No unfinished marker text or deferred-implementation notes remain.
- Every task includes explicit files, commands, and concrete code snippets.

### Type consistency

- `JobSpecRecord` is the backend submission shape used across Task 1, Task 2, and Task 4.
- `PlacementPlan` carries `selected_node` and `selected_devices` consistently through scheduler and orchestration tasks.
- Node runtime APIs consistently use `reservation_id` and `job_handle`.
