# Runtime Control And App-Managed Checkpoint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade cluster jobs from ledger-only lifecycle changes into real runtime-controlled jobs with working `pause/resume` and app-managed `checkpoint/restore`.

**Architecture:** Keep the existing `cluster_control -> execution_orchestrator -> execution_backend -> server-agent runtime` chain. First make `job.pause/job.resume` drive real node runtime actions, then layer an app-managed checkpoint contract on top of the same runtime job model, persist checkpoint metadata in cluster storage, and expose the new states through shared Agent/manual controls and the compact cluster console.

**Tech Stack:** FastAPI, Python, `aiosqlite`, `psutil`, Vue 3, Vite, Node `node:test`, `pytest`, Windows-first verification via `cmd.exe`.

---

## Planned File Map

- `server-agent/runtime_store.py`
  - Extend runtime job records with pause/checkpoint metadata and add focused mutation helpers.
- `server-agent/job_runtime.py`
  - Add real runtime job actions: `pause`, `resume`, `request_checkpoint`, `restore`, checkpoint polling helpers, and restore-aware launch env.
- `server-agent/main.py`
  - Expose the new runtime endpoints and payload schemas.
- `backend/app/services/cluster_control/execution_backend.py`
  - Extend `HTTPAgentProcessBackend` with `get_job`, `pause_job`, `resume_job`, `checkpoint_job`, `get_checkpoint`, and `restore_job`.
- `backend/app/services/cluster_control/execution_orchestrator.py`
  - Add runtime control helpers which keep control-plane callers backend-agnostic.
- `backend/app/services/cluster_control/sqlite_support.py`
  - Add checkpoint pointer columns and a new `cluster_checkpoints` table.
- `backend/app/services/data_store.py`
  - Add CRUD helpers for checkpoint records and job checkpoint pointer updates.
- `backend/app/services/cluster_control/control_plane_job_actions.py`
  - Add `pause_running_job`, `resume_paused_job`, `request_checkpoint_for_job`, and `restore_checkpointed_job`.
- `backend/app/services/cluster_control/control_plane.py`
  - Route real job-control actions through the orchestrator instead of only changing store state.
- `backend/app/services/cluster_control/runtime_feedback.py`
  - Reconcile runtime pause/checkpoint/restore states back into cluster jobs and allocations.
- `backend/app/models/schemas.py`
  - Add request models for checkpoint and restore actions.
- `backend/app/api/cluster_jobs.py`
  - Expose cluster REST endpoints for `pause`, `resume`, `checkpoint`, and `restore`.
- `backend/app/services/goal_runtime/cluster_execution_capabilities.py`
  - Register `job.checkpoint` and `job.restore`.
- `backend/app/services/goal_runtime/planner.py`
  - Map `checkpoint_job` and `restore_job` actions to the new capabilities.
- `backend/app/services/goal_runtime/goal_parser.py`
  - Treat checkpoint/restore as runtime job actions for `done_when`.
- `backend/app/services/goal_runtime/control_heuristic_support.py`
  - Add keyword extraction for checkpoint/restore job intents.
- `frontend/src/lib/controlCapabilityForms.js`
  - Add typed manual forms for `job.checkpoint` and `job.restore`.
- `frontend/src/lib/clusterConsoleActions.js`
  - Add `checkpoint` and `restore` action labels and capability mapping.
- `frontend/src/lib/clusterConsoleModels.js`
  - Project checkpoint metadata and new lifecycle states into the compact view model.
- `frontend/src/components/cluster/ClusterJobLedger.vue`
  - Surface checkpoint/restore actions and compact checkpoint status rows.
- `tests/test_node_runtime_api.py`
  - Cover runtime pause/resume, checkpoint request/result flow, and restore launch.
- `tests/test_cluster_scheduler_core.py`
  - Extend existing orchestrator tests to cover the new backend methods.
- `tests/test_cluster_job_api.py`
  - Cover cluster job pause/resume/checkpoint/restore state transitions and checkpoint persistence.
- `tests/test_goal_runtime_cluster_capabilities.py`
  - Cover `job.checkpoint` and `job.restore` capability registration.
- `tests/test_goal_runtime_planner.py`
  - Cover planner mapping for checkpoint/restore actions.
- `frontend/src/lib/controlCapabilityModels.test.js`
  - Cover new manual capability form serialization.
- `frontend/src/lib/clusterConsoleModels.test.js`
  - Cover compact checkpoint state projection.

### Task 1: Write Red Tests For Runtime Pause, Resume, Checkpoint, And Restore

**Files:**
- Modify: `tests/test_node_runtime_api.py`
- Modify: `tests/test_cluster_scheduler_core.py`
- Modify: `tests/test_cluster_job_api.py`

- [ ] **Step 1: Add failing node runtime API tests for `pause` and `resume`**

```python
def test_pause_and_resume_runtime_job_by_handle(self):
    with TestClient(app) as client:
        client.post(
            "/api/runtime/reservations",
            json={
                "reservation_id": "res-pause",
                "job_id": "job-pause",
                "gpu_indexes": [0],
                "cpu_cores": [],
            },
        )
        client.post(
            "/api/runtime/jobs/launch",
            json={
                "job_handle": "handle-pause",
                "job_id": "job-pause",
                "reservation_id": "res-pause",
                "command": SLEEP_COMMAND,
                "env": {},
            },
        )

        paused = client.post("/api/runtime/jobs/handle-pause/pause")
        resumed = client.post("/api/runtime/jobs/handle-pause/resume")

    self.assertEqual(paused.status_code, 200)
    self.assertEqual(paused.json()["state"], "paused")
    self.assertEqual(resumed.status_code, 200)
    self.assertEqual(resumed.json()["state"], "running")
```

- [ ] **Step 2: Add failing node runtime API tests for app-managed checkpoint contract**

```python
def test_checkpoint_request_creates_pending_checkpoint_state(self):
    with TestClient(app) as client:
        client.post(
            "/api/runtime/reservations",
            json={
                "reservation_id": "res-ckpt",
                "job_id": "job-ckpt",
                "gpu_indexes": [0],
                "cpu_cores": [],
            },
        )
        client.post(
            "/api/runtime/jobs/launch",
            json={
                "job_handle": "handle-ckpt",
                "job_id": "job-ckpt",
                "reservation_id": "res-ckpt",
                "command": SLEEP_COMMAND,
                "env": {},
                "checkpoint_policy": "app_managed",
            },
        )

        response = client.post(
            "/api/runtime/jobs/handle-ckpt/checkpoint",
            json={"checkpoint_id": "ckpt-1", "timeout_seconds": 15},
        )
        details = client.get("/api/runtime/jobs/handle-ckpt/checkpoint")

    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.json()["checkpoint_state"], "checkpoint_requested")
    self.assertEqual(details.json()["checkpoint_id"], "ckpt-1")
```

- [ ] **Step 3: Add failing node runtime API tests for restore launch**

```python
def test_restore_runtime_job_uses_manifest_env(self):
    with TestClient(app) as client:
        restore = client.post(
            "/api/runtime/jobs/handle-restore/restore",
            json={
                "job_handle": "handle-restore",
                "job_id": "job-restore",
                "reservation_id": "res-restore",
                "checkpoint_id": "ckpt-restore",
                "manifest_path": "C:/tmp/aidc/ckpt.json",
                "command": COMPLETE_COMMAND,
                "env": {},
            },
        )

    self.assertEqual(restore.status_code, 200)
    self.assertEqual(restore.json()["state"], "restoring")
```

- [ ] **Step 4: Add failing orchestrator tests for the new runtime backend methods**

```python
async def test_orchestrator_forwards_pause_resume_checkpoint_restore(self):
    backend = _FakeBackend()
    orchestrator = ExecutionOrchestrator(store, {"http_agent": backend})

    await orchestrator.pause_runtime_job(node_a, "handle-1")
    await orchestrator.resume_runtime_job(node_a, "handle-1")
    await orchestrator.checkpoint_runtime_job(
        node_a,
        "handle-1",
        {"checkpoint_id": "ckpt-1", "timeout_seconds": 15},
    )
    await orchestrator.restore_runtime_job(
        node_a,
        {"job_handle": "handle-2", "checkpoint_id": "ckpt-1"},
    )

    assert backend.calls == [
        ("pause", "handle-1"),
        ("resume", "handle-1"),
        ("checkpoint", "handle-1", "ckpt-1"),
        ("restore", "handle-2", "ckpt-1"),
    ]
```

- [ ] **Step 5: Add failing cluster job API tests for pause/resume/checkpoint/restore**

```python
async def test_cluster_job_pause_resume_checkpoint_restore_routes_drive_control_plane(self):
    paused = await pause_cluster_job("job-1")
    resumed = await resume_cluster_job("job-1")
    checkpointed = await checkpoint_cluster_job("job-1", ClusterJobCheckpointRequest())
    restored = await restore_cluster_job("job-1", ClusterJobRestoreRequest())

    self.assertEqual(paused["status"], "paused")
    self.assertEqual(resumed["status"], "running")
    self.assertEqual(checkpointed["checkpoint_status"], "checkpoint_requested")
    self.assertEqual(restored["status"], "restoring")
```

- [ ] **Step 6: Run focused backend red tests**
Run: `timeout 60s cmd.exe /c "E:\Code\AI-DataCenter\.venv\Scripts\python.exe -m pytest tests\test_node_runtime_api.py tests\test_cluster_scheduler_core.py tests\test_cluster_job_api.py -q"`
Expected: FAIL with missing runtime endpoints, missing orchestrator methods, and missing checkpoint/restore cluster handlers.

- [ ] **Step 7: Commit**

```bash
git add tests/test_node_runtime_api.py tests/test_cluster_scheduler_core.py tests/test_cluster_job_api.py
git commit -m "test: cover runtime control and checkpoint red paths"
```

### Task 2: Implement Node Runtime State And API

**Files:**
- Modify: `server-agent/runtime_store.py`
- Modify: `server-agent/job_runtime.py`
- Modify: `server-agent/main.py`
- Test: `tests/test_node_runtime_api.py`

- [ ] **Step 1: Extend runtime store with pause/checkpoint metadata helpers**

```python
def update_job_pause_state(self, job_handle: str, *, state: str, timestamp: float) -> dict:
    with self._lock:
        item = dict(self._jobs.get(job_handle) or {})
        if not item:
            raise KeyError(job_handle)
        item["state"] = state
        if state == "paused":
            item["paused_at"] = timestamp
        else:
            item["resumed_at"] = timestamp
        self._jobs[job_handle] = item
    return dict(item)

def update_job_checkpoint(self, job_handle: str, **changes) -> dict:
    with self._lock:
        item = dict(self._jobs.get(job_handle) or {})
        if not item:
            raise KeyError(job_handle)
        item.update(changes)
        self._jobs[job_handle] = item
    return dict(item)
```

- [ ] **Step 2: Implement runtime pause/resume/checkpoint/restore methods**

```python
def pause(self, job_handle: str) -> dict | None:
    process = self._require_process(job_handle)
    psutil.Process(process.pid).suspend()
    return self.store.update_job_pause_state(
        job_handle,
        state="paused",
        timestamp=time.time(),
    )

def request_checkpoint(self, job_handle: str, payload: dict) -> dict | None:
    item = self.store.get_job(job_handle)
    if item is None:
        return None
    if str(item.get("checkpoint_policy") or "") != "app_managed":
        raise ValueError("runtime job does not support app-managed checkpoint")
    control_dir = self._ensure_control_dir(item)
    request_path = os.path.join(control_dir, "checkpoint-request.json")
    with open(request_path, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "checkpoint_id": payload["checkpoint_id"],
                "artifact_root": item["artifact_root"],
                "timeout_seconds": payload["timeout_seconds"],
                "requested_at": time.time(),
            },
            handle,
            ensure_ascii=False,
        )
    return self.store.update_job_checkpoint(
        job_handle,
        checkpoint_state="checkpoint_requested",
        checkpoint_id=str(payload["checkpoint_id"]),
    )
```

- [ ] **Step 3: Inject control/artifact env on launch and restore**

```python
def _runtime_paths(self, job_handle: str) -> dict[str, str]:
    root = os.path.join(self._runtime_root, job_handle)
    return {
        "root": root,
        "control_dir": os.path.join(root, "control"),
        "artifact_root": os.path.join(root, "artifacts"),
    }

def _build_env(self, overrides: dict | None, runtime_meta: dict) -> dict[str, str]:
    env = dict(os.environ)
    env.update({str(key): str(value) for key, value in (overrides or {}).items()})
    env["AIDC_JOB_HANDLE"] = runtime_meta["job_handle"]
    env["AIDC_JOB_ID"] = runtime_meta["job_id"]
    env["AIDC_CONTROL_DIR"] = runtime_meta["control_dir"]
    env["AIDC_ARTIFACT_ROOT"] = runtime_meta["artifact_root"]
    if runtime_meta.get("restore_from"):
        env["AIDC_RESTORE_FROM"] = runtime_meta["restore_from"]
    return env
```

- [ ] **Step 4: Add FastAPI schemas and routes for runtime control**

```python
class RuntimeCheckpointRequest(BaseModel):
    checkpoint_id: str = Field(min_length=1, max_length=120)
    timeout_seconds: int = Field(default=30, ge=1, le=3600)
    reason: str = Field(default="", max_length=500)

@app.post("/api/runtime/jobs/{job_handle}/pause")
def pause_runtime_job(job_handle: str):
    item = job_runtime.pause(job_handle)
    if item is None:
        raise HTTPException(status_code=404, detail="runtime job not found")
    return item
```

- [ ] **Step 5: Run focused runtime tests to green**
Run: `timeout 60s cmd.exe /c "E:\Code\AI-DataCenter\.venv\Scripts\python.exe -m pytest tests\test_node_runtime_api.py -q"`
Expected: PASS with new runtime control endpoints and app-managed checkpoint state flow.

- [ ] **Step 6: Commit**

```bash
git add server-agent/runtime_store.py server-agent/job_runtime.py server-agent/main.py tests/test_node_runtime_api.py
git commit -m "feat: add runtime pause resume checkpoint restore api"
```

### Task 3: Extend Execution Backend And Orchestrator

**Files:**
- Modify: `backend/app/services/cluster_control/execution_backend.py`
- Modify: `backend/app/services/cluster_control/execution_orchestrator.py`
- Test: `tests/test_cluster_scheduler_core.py`

- [ ] **Step 1: Add HTTP runtime control methods to the backend**

```python
async def pause_job(self, node: dict, job_handle: str) -> dict:
    return await self._post(node, f"/api/runtime/jobs/{job_handle}/pause", {})

async def checkpoint_job(self, node: dict, job_handle: str, payload: dict) -> dict:
    return await self._post(node, f"/api/runtime/jobs/{job_handle}/checkpoint", payload)

async def restore_job(self, node: dict, payload: dict) -> dict:
    job_handle = str(payload["job_handle"])
    return await self._post(node, f"/api/runtime/jobs/{job_handle}/restore", payload)
```

- [ ] **Step 2: Add orchestrator façade methods for runtime control**

```python
async def pause_runtime_job(self, node: dict, job_handle: str) -> dict:
    backend = self._require_backend(str(node.get("execution_backend") or "http_agent"))
    return await backend.pause_job(node, job_handle)

async def get_runtime_checkpoint(self, node: dict, job_handle: str) -> dict:
    backend = self._require_backend(str(node.get("execution_backend") or "http_agent"))
    return await backend.get_checkpoint(node, job_handle)
```

- [ ] **Step 3: Keep restore payload aligned with launch payload shape**

```python
def build_restore_payload(
    self,
    job_record: JobSpecRecord,
    reservation_id: str,
    checkpoint_id: str,
    manifest_path: str,
) -> dict:
    return {
        **self._launch_payload(job_record, reservation_id),
        "checkpoint_id": checkpoint_id,
        "manifest_path": manifest_path,
    }
```

- [ ] **Step 4: Run focused orchestrator tests to green**
Run: `timeout 60s cmd.exe /c "E:\Code\AI-DataCenter\.venv\Scripts\python.exe -m pytest tests\test_cluster_scheduler_core.py -q"`
Expected: PASS with new backend/orchestrator control methods covered.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/cluster_control/execution_backend.py backend/app/services/cluster_control/execution_orchestrator.py tests/test_cluster_scheduler_core.py
git commit -m "feat: extend execution backend for runtime control"
```

### Task 4: Persist Checkpoints And Route Cluster Job Actions Through Real Runtime Control

**Files:**
- Modify: `backend/app/services/cluster_control/sqlite_support.py`
- Modify: `backend/app/services/data_store.py`
- Modify: `backend/app/services/cluster_control/control_plane_job_actions.py`
- Modify: `backend/app/services/cluster_control/control_plane.py`
- Modify: `backend/app/services/cluster_control/runtime_feedback.py`
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/api/cluster_jobs.py`
- Test: `tests/test_cluster_job_api.py`

- [ ] **Step 1: Add checkpoint table and pointer fields**

```python
CREATE TABLE IF NOT EXISTS cluster_checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    allocation_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    status TEXT NOT NULL,
    manifest_path TEXT NOT NULL DEFAULT '',
    artifact_paths_json TEXT NOT NULL DEFAULT '[]',
    error TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
```

```python
"ALTER TABLE cluster_jobs ADD COLUMN checkpoint_id TEXT NOT NULL DEFAULT ''",
"ALTER TABLE cluster_jobs ADD COLUMN checkpoint_status TEXT NOT NULL DEFAULT ''",
"ALTER TABLE cluster_jobs ADD COLUMN checkpoint_manifest_path TEXT NOT NULL DEFAULT ''",
"ALTER TABLE cluster_jobs ADD COLUMN checkpoint_error TEXT NOT NULL DEFAULT ''",
"ALTER TABLE cluster_jobs ADD COLUMN checkpoint_updated_at REAL NOT NULL DEFAULT 0",
```

- [ ] **Step 2: Add focused data-store helpers**

```python
async def create_cluster_checkpoint(self, payload: dict) -> None:
    db = require_cluster_db(self._db)
    await create_checkpoint_record(db, payload)

async def update_cluster_job_checkpoint(self, job_id: str, **changes) -> None:
    db = require_cluster_db(self._db)
    await update_job_checkpoint_record(db, job_id, changes)
```

- [ ] **Step 3: Replace ledger-only pause/resume with real runtime job actions**

```python
async def pause_running_job(store, orchestrator, job_loader, job: dict) -> dict:
    allocation = await find_active_allocation_for_job(store, str(job["job_id"]))
    if allocation is None:
        raise ValueError(f"running job missing active allocation: {job['job_id']}")
    node = await store.get_cluster_node(str(allocation["node_id"]))
    runtime_job = await orchestrator.pause_runtime_job(
        node,
        str(allocation["runtime_job_handle"]),
    )
    await store.update_cluster_job_state(str(job["job_id"]), "paused", execution_backend=str(allocation.get("execution_backend") or ""))
    await store.update_cluster_allocations_for_job(str(job["job_id"]), "paused")
    return await job_loader(str(job["job_id"]))
```

- [ ] **Step 4: Add checkpoint and restore control-plane methods**

```python
async def checkpoint_job(self, job_id: str) -> dict:
    job = await self.store.get_cluster_job(job_id)
    if job is None:
        raise LookupError(f"cluster job not found: {job_id}")
    return await request_checkpoint_for_job(
        self.store,
        self.orchestrator,
        self.get_job,
        job,
    )

async def restore_job(self, job_id: str, *, checkpoint_id: str = "") -> dict:
    job = await self.store.get_cluster_job(job_id)
    if job is None:
        raise LookupError(f"cluster job not found: {job_id}")
    return await restore_checkpointed_job(
        self.store,
        self.orchestrator,
        self.get_job,
        job,
        checkpoint_id=checkpoint_id,
    )
```

- [ ] **Step 5: Expose cluster REST routes and request models**

```python
class ClusterJobCheckpointRequest(BaseModel):
    timeout_seconds: int = Field(default=30, ge=1, le=3600)

class ClusterJobRestoreRequest(BaseModel):
    checkpoint_id: str = Field(default="", max_length=120)

@router.post("/jobs/{job_id}/checkpoint")
async def checkpoint_cluster_job(job_id: str, req: ClusterJobCheckpointRequest):
    from app.main import app_state
    return await app_state.cluster_control.checkpoint_job(job_id)
```

- [ ] **Step 6: Run focused cluster job API tests to green**
Run: `timeout 60s cmd.exe /c "E:\Code\AI-DataCenter\.venv\Scripts\python.exe -m pytest tests\test_cluster_job_api.py -q"`
Expected: PASS with real cluster pause/resume/checkpoint/restore transitions and persisted checkpoint metadata.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/cluster_control/sqlite_support.py backend/app/services/data_store.py backend/app/services/cluster_control/control_plane_job_actions.py backend/app/services/cluster_control/control_plane.py backend/app/services/cluster_control/runtime_feedback.py backend/app/models/schemas.py backend/app/api/cluster_jobs.py tests/test_cluster_job_api.py
git commit -m "feat: persist checkpoints and real cluster job runtime control"
```

### Task 5: Register Agent And Manual Capabilities For Checkpoint And Restore

**Files:**
- Modify: `backend/app/services/goal_runtime/cluster_execution_capabilities.py`
- Modify: `backend/app/services/goal_runtime/planner.py`
- Modify: `backend/app/services/goal_runtime/goal_parser.py`
- Modify: `backend/app/services/goal_runtime/control_heuristic_support.py`
- Test: `tests/test_goal_runtime_cluster_capabilities.py`
- Test: `tests/test_goal_runtime_planner.py`

- [ ] **Step 1: Add failing capability and planner tests**

```python
def test_cluster_execution_capabilities_include_checkpoint_and_restore():
    registry = build_platform_capability_registry(_build_state())

    assert registry.get("job.checkpoint").definition.domain == "jobs"
    assert registry.get("job.restore").definition.domain == "jobs"
```

```python
def test_planner_maps_checkpoint_and_restore_actions():
    goal_spec = GoalSpec(
        session_id="sess-1",
        raw_message="给 job-1 做检查点并恢复",
        goal_type="runtime_control",
        permission_mode="low",
        scope_gpu_indexes=(),
        constraints=(),
        done_when="job_state_updated",
        abort_when=("no_capability_path",),
        planner_actions=(
            {"action": "checkpoint_job", "target": {"job_id": "job-1"}},
            {"action": "restore_job", "target": {"job_id": "job-1"}},
        ),
        planner_summary="checkpoint and restore",
        planner_source="rule",
    )

    plan = build_initial_plan(goal_spec, registry)
    assert [step.capability_name for step in plan.steps[1:]] == ["job.checkpoint", "job.restore"]
```

- [ ] **Step 2: Register checkpoint/restore capabilities**

```python
async def checkpoint_job(_context, arguments):
    return await app_state.cluster_control.checkpoint_job(str(arguments["job_id"]))

async def restore_job(_context, arguments):
    return await app_state.cluster_control.restore_job(
        str(arguments["job_id"]),
        checkpoint_id=str(arguments.get("checkpoint_id") or ""),
    )
```

- [ ] **Step 3: Extend planner and heuristics**

```python
ACTION_CAPABILITY_MAP = {
    **ACTION_CAPABILITY_MAP,
    "checkpoint_job": "job.checkpoint",
    "restore_job": "job.restore",
}
```

```python
if any(word in text for word in ("检查点", "保存进度", "checkpoint")):
    return [
        {
            "action": "checkpoint_job",
            "target": {"job_id": job_id},
            "reason": f"根据用户指令为作业 {job_id} 创建检查点",
        }
    ]
```

- [ ] **Step 4: Run focused capability/planner tests to green**
Run: `timeout 60s cmd.exe /c "E:\Code\AI-DataCenter\.venv\Scripts\python.exe -m pytest tests\test_goal_runtime_cluster_capabilities.py tests\test_goal_runtime_planner.py -q"`
Expected: PASS with `job.checkpoint` and `job.restore` registered and reachable through planner mapping.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/goal_runtime/cluster_execution_capabilities.py backend/app/services/goal_runtime/planner.py backend/app/services/goal_runtime/goal_parser.py backend/app/services/goal_runtime/control_heuristic_support.py tests/test_goal_runtime_cluster_capabilities.py tests/test_goal_runtime_planner.py
git commit -m "feat: add checkpoint restore goal runtime capabilities"
```

### Task 6: Add Manual Forms And Compact Cluster Console Checkpoint UI

**Files:**
- Modify: `frontend/src/lib/controlCapabilityForms.js`
- Modify: `frontend/src/lib/clusterConsoleActions.js`
- Modify: `frontend/src/lib/clusterConsoleModels.js`
- Modify: `frontend/src/components/cluster/ClusterJobLedger.vue`
- Test: `frontend/src/lib/controlCapabilityModels.test.js`
- Test: `frontend/src/lib/clusterConsoleModels.test.js`

- [ ] **Step 1: Add failing frontend tests**

```javascript
test('buildCapabilityFormDraft exposes checkpoint and restore job forms', () => {
  assert.equal(buildCapabilityFormDraft('job.checkpoint').job_id, '')
  assert.equal(buildCapabilityFormDraft('job.restore').job_id, '')
})
```

```javascript
test('buildClusterConsoleModel projects checkpoint metadata compactly', () => {
  const model = buildClusterConsoleModel({
    jobs: [{
      job_id: 'job-1',
      status: 'checkpoint_ready',
      checkpoint_id: 'ckpt-1',
      checkpoint_status: 'checkpoint_ready',
      checkpoint_manifest_path: '/tmp/ckpt-1.json',
    }],
    allocations: [],
    queues: [],
    nodes: [],
    controller: {},
  })

  assert.equal(model.jobs[0].checkpointStatus, 'checkpoint_ready')
  assert.equal(model.jobs[0].checkpointId, 'ckpt-1')
})
```

- [ ] **Step 2: Add manual capability forms and job action labels**

```javascript
'job.checkpoint': {
  kind: 'job.checkpoint',
  fields: [
    field('job_id', '作业 ID', 'text', { cast: 'string', defaultValue: '' }),
    field('timeout_seconds', '检查点超时(s)', 'number', { cast: 'int', defaultValue: 30, required: false }),
  ],
},
'job.restore': {
  kind: 'job.restore',
  fields: [
    field('job_id', '作业 ID', 'text', { cast: 'string', defaultValue: '' }),
    field('checkpoint_id', '检查点 ID', 'text', { cast: 'string', defaultValue: '', required: false }),
  ],
},
```

```javascript
const ACTION_CAPABILITIES = Object.freeze({
  pause: 'job.pause',
  resume: 'job.resume',
  checkpoint: 'job.checkpoint',
  restore: 'job.restore',
  cancel: 'job.cancel',
  requeue: 'job.requeue',
  preempt: 'job.preempt',
})
```

- [ ] **Step 3: Project compact checkpoint info and render new actions**

```javascript
return {
  id: job.job_id,
  status: job.status,
  checkpointStatus: job.checkpoint_status || '',
  checkpointId: job.checkpoint_id || '',
  checkpointManifestPath: job.checkpoint_manifest_path || '',
  checkpointError: job.checkpoint_error || '',
}
```

```javascript
if (job.status === 'running' || job.status === 'ready') {
  return ['pause', 'checkpoint', 'requeue', 'preempt', 'cancel']
}
if (job.status === 'checkpoint_ready') {
  return ['restore', 'requeue']
}
```

- [ ] **Step 4: Run focused frontend tests**
Run: `cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm test -- src\lib\controlCapabilityModels.test.js src\lib\clusterConsoleModels.test.js"`
Expected: PASS with manual capability drafts and compact checkpoint projection working.

- [ ] **Step 5: Run frontend production build**
Run: `cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm run build"`
Expected: PASS with no new TypeError or unknown action errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/controlCapabilityForms.js frontend/src/lib/clusterConsoleActions.js frontend/src/lib/clusterConsoleModels.js frontend/src/components/cluster/ClusterJobLedger.vue frontend/src/lib/controlCapabilityModels.test.js frontend/src/lib/clusterConsoleModels.test.js
git commit -m "feat: surface checkpoint restore controls in cluster console"
```

### Task 7: Run End-To-End Verification On Windows Paths

**Files:**
- Modify: `docs/superpowers/plans/2026-04-11-runtime-control-and-app-managed-checkpoint.md`

- [ ] **Step 1: Run the targeted backend regression suite**
Run: `timeout 60s cmd.exe /c "E:\Code\AI-DataCenter\.venv\Scripts\python.exe -m pytest tests\test_node_runtime_api.py tests\test_cluster_scheduler_core.py tests\test_cluster_job_api.py tests\test_goal_runtime_cluster_capabilities.py tests\test_goal_runtime_planner.py -q"`
Expected: PASS for runtime API, orchestrator, cluster API, and Agent capability coverage.

- [ ] **Step 2: Run frontend targeted tests and build**
Run: `cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm test -- src\lib\controlCapabilityModels.test.js src\lib\clusterConsoleModels.test.js && npm run build"`
Expected: PASS with no action-map or view-model regression.

- [ ] **Step 3: Run backend static compile check**
Run: `cmd.exe /c "cd /d E:\Code\AI-DataCenter && .venv\\Scripts\\python.exe -m compileall backend\\app server-agent"`
Expected: PASS with no syntax errors.

- [ ] **Step 4: Update the plan checklist and commit the completed implementation**

```bash
git add backend server-agent frontend tests
git commit -m "feat: add runtime control and app-managed checkpoint workflow"
```

## Self-Review

- Spec coverage:
  - Runtime protocol: covered by Tasks 1-3.
  - Checkpoint persistence and cluster state: covered by Task 4.
  - Agent/manual capability surfacing: covered by Task 5.
  - Frontend compact UI: covered by Task 6.
  - Windows verification: covered by Task 7.
- Placeholder scan:
  - 计划正文中没有未完成标记或悬空说明。
  - Each task includes exact file paths, test commands, and concrete code sketches.
- Type consistency:
  - Runtime method names are consistently `pause_runtime_job`, `resume_runtime_job`, `checkpoint_runtime_job`, `restore_runtime_job`.
  - Capability names are consistently `job.checkpoint` and `job.restore`.
  - Planner action names are consistently `checkpoint_job` and `restore_job`.
