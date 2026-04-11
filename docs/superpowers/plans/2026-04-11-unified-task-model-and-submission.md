# Unified Task Model And Submission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the existing `JobSpec` path into a unified multi-task submission slice that supports training, inference services, interactive sessions, batch compute, and maintenance jobs across manual control and Agent runtime.

**Architecture:** Keep `cluster_control` and `job.submit` as the single source of truth. Extend the backend schema and persistence first, then teach `ClusterSchedulerCore` to consume task semantics, then propagate the new fields through `execution_orchestrator -> HTTPAgentProcessBackend -> server-agent job_runtime`, and finally lift the manual submission UI and Agent planner onto the same task model.

**Tech Stack:** FastAPI, Python dataclasses, `aiosqlite`, Vue 3, Node `node:test`, `pytest`, server-agent FastAPI runtime.

---

## Planned File Map

- `backend/app/models/schemas.py`
  - Expand request/response schema for unified task fields.
- `backend/app/services/cluster_control/models.py`
  - Extend `JobSpecRecord` with first-phase task semantics.
- `backend/app/services/cluster_control/sqlite_support.py`
  - Persist unified task fields on cluster jobs and allocations.
- `backend/app/services/data_store.py`
  - Surface the new persistence helpers through the store layer.
- `backend/app/api/cluster_jobs.py`
  - Accept the new submit payload and expose richer job responses.
- `backend/app/services/cluster_control/control_plane.py`
  - Pass the richer job model through plan/submit flows and use allocation context during scheduling.
- `backend/app/services/cluster_control/scheduler_core.py`
  - Add hard constraints and light scoring for task/lifecycle/service-port semantics.
- `backend/app/services/cluster_control/execution_orchestrator.py`
  - Pass unified task metadata and service port declarations to node runtime launch payloads.
- `backend/app/services/cluster_control/execution_backend.py`
  - Keep backend interface explicit while forwarding richer runtime payloads through `http_agent`.
- `server-agent/runtime_store.py`
  - Persist richer runtime job snapshots including readiness and task metadata.
- `server-agent/job_runtime.py`
  - Track task kind, lifecycle kind, service ports, readiness, and health in runtime job records.
- `server-agent/main.py`
  - Accept richer runtime job launch payloads and expose them via runtime job listing.
- `backend/app/services/goal_runtime/control_heuristic_support.py`
  - Add first-phase `submit_job` extraction for common multi-task intents.
- `backend/app/services/goal_runtime/control_heuristics.py`
  - Include submit heuristics in planner fallback extraction.
- `backend/app/services/goal_runtime/planner.py`
  - Keep `submit_job -> job.submit` path stable once heuristics emit it.
- `backend/app/services/goal_runtime/platform_capabilities.py`
  - Build richer `JobSpecRecord` objects from `job.submit` arguments.
- `frontend/src/lib/controlCapabilityForms.js`
  - Replace the compact training-biased `job.submit` form with a task-kind-driven form.
- `frontend/src/lib/controlCapabilityModels.js`
  - Summarize richer submit payloads in the control ledger and preview.
- `frontend/src/lib/clusterConsoleModels.js`
  - Map unified task fields and readiness state into cluster console view models.
- `frontend/src/components/governance/CapabilityCommandDrawer.vue`
  - Render the dynamic task-kind-aware manual submit form.
- `frontend/src/components/cluster/ClusterJobLedger.vue`
  - Reflect unified task labels and remove training-only assumptions.
- `tests/test_cluster_job_api.py`
  - Cover the enriched cluster job submit/request-response path.
- `tests/test_cluster_scheduler_core.py`
  - Cover task semantics, port conflicts, exclusivity, and lifecycle scoring.
- `tests/test_node_runtime_api.py`
  - Cover richer runtime job launch/list payloads and readiness state.
- `tests/test_goal_runtime_capabilities.py`
  - Cover `job.submit` capability accepting the richer payload.
- `tests/test_goal_runtime_planner.py`
  - Cover rule-based `submit_job` planning for common task kinds.
- `frontend/src/lib/controlCapabilityModels.test.js`
  - Cover the new manual `job.submit` form draft/serialization behavior.
- `frontend/src/lib/clusterConsoleModels.test.js`
  - Cover cluster console mapping of task kind, lifecycle, and readiness.

### Task 1: Write Red Tests For Unified Task Submission

**Files:**
- Modify: `tests/test_cluster_job_api.py`
- Modify: `tests/test_cluster_scheduler_core.py`
- Modify: `tests/test_node_runtime_api.py`
- Modify: `tests/test_goal_runtime_capabilities.py`
- Modify: `tests/test_goal_runtime_planner.py`
- Modify: `frontend/src/lib/controlCapabilityModels.test.js`
- Modify: `frontend/src/lib/clusterConsoleModels.test.js`

- [ ] **Step 1: Add failing backend API tests for unified submit payloads**
- [ ] **Step 2: Add failing scheduler tests for service-port conflict, lifecycle fit, and exclusive GPU semantics**
- [ ] **Step 3: Add failing node runtime API tests for richer runtime job fields and `ready` state**
- [ ] **Step 4: Add failing Agent capability/planner tests for `submit_job` requests across common task kinds**
- [ ] **Step 5: Add failing frontend tests for task-kind-driven manual forms and cluster row summaries**
- [ ] **Step 6: Run focused red tests**
Run: `timeout 60s cmd.exe /c "E:\Code\AI-DataCenter\.venv\Scripts\python.exe -m pytest tests\test_cluster_job_api.py tests\test_cluster_scheduler_core.py tests\test_node_runtime_api.py tests\test_goal_runtime_capabilities.py tests\test_goal_runtime_planner.py -q"`
Expected: FAIL in the new unified-task assertions.
Run: `cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm test -- src\lib\controlCapabilityModels.test.js src\lib\clusterConsoleModels.test.js"`
Expected: FAIL in the new submit-form and cluster-model assertions.

### Task 2: Extend Backend Task Schema And Persistence

**Files:**
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/services/cluster_control/models.py`
- Modify: `backend/app/services/cluster_control/sqlite_support.py`
- Modify: `backend/app/services/data_store.py`
- Modify: `backend/app/api/cluster_jobs.py`
- Modify: `backend/app/services/goal_runtime/platform_capabilities.py`

- [ ] **Step 1: Add unified task fields to API schema models**
- [ ] **Step 2: Extend `JobSpecRecord` with `task_kind`, `lifecycle_kind`, `service_ports`, `checkpoint_policy`, and `runtime_profile`**
- [ ] **Step 3: Persist the new fields on cluster jobs and normalize them on reads**
- [ ] **Step 4: Keep submit defaults explicit so old callers still serialize to a valid first-phase task model**
- [ ] **Step 5: Make `job.submit` capability build the richer `JobSpecRecord`**
- [ ] **Step 6: Run focused backend tests green**
Run: `timeout 60s cmd.exe /c "E:\Code\AI-DataCenter\.venv\Scripts\python.exe -m pytest tests\test_cluster_job_api.py tests\test_goal_runtime_capabilities.py -q"`
Expected: PASS.

### Task 3: Teach The Scheduler To Consume Task Semantics

**Files:**
- Modify: `backend/app/services/cluster_control/scheduler_core.py`
- Modify: `backend/app/services/cluster_control/control_plane.py`
- Modify: `backend/app/api/cluster_jobs.py`

- [ ] **Step 1: Thread active allocation context into planning so scheduler can see occupied ports and active GPU bindings**
- [ ] **Step 2: Add hard constraints for service-port conflict, lifecycle compatibility, and exclusive GPU**
- [ ] **Step 3: Add first-phase light scoring for `service`, `session`, restartable `batch`, and `maintenance` jobs**
- [ ] **Step 4: Keep queue admission behavior intact while enriching plan reasons for new task semantics**
- [ ] **Step 5: Run focused scheduler tests green**
Run: `timeout 60s cmd.exe /c "E:\Code\AI-DataCenter\.venv\Scripts\python.exe -m pytest tests\test_cluster_scheduler_core.py tests\test_cluster_job_api.py -q"`
Expected: PASS.

### Task 4: Propagate Unified Task Runtime State Through HTTP Agent

**Files:**
- Modify: `backend/app/services/cluster_control/execution_orchestrator.py`
- Modify: `backend/app/services/cluster_control/execution_backend.py`
- Modify: `server-agent/runtime_store.py`
- Modify: `server-agent/job_runtime.py`
- Modify: `server-agent/main.py`

- [ ] **Step 1: Add unified task metadata and service port declarations to launch payloads**
- [ ] **Step 2: Persist richer runtime job records on the node agent**
- [ ] **Step 3: Add minimal readiness detection: port-declared jobs can become `ready`, non-port jobs stay `running`**
- [ ] **Step 4: Keep cancel semantics real and leave unsupported lifecycle actions explicit**
- [ ] **Step 5: Run focused node runtime tests green**
Run: `timeout 60s cmd.exe /c "E:\Code\AI-DataCenter\.venv\Scripts\python.exe -m pytest tests\test_node_runtime_api.py tests\test_cluster_job_api.py -q"`
Expected: PASS.

### Task 5: Upgrade Manual Submission UI To A Task-Kind-Driven Form

**Files:**
- Modify: `frontend/src/lib/controlCapabilityForms.js`
- Modify: `frontend/src/lib/controlCapabilityModels.js`
- Modify: `frontend/src/lib/clusterConsoleModels.js`
- Modify: `frontend/src/components/governance/CapabilityCommandDrawer.vue`
- Modify: `frontend/src/components/cluster/ClusterJobLedger.vue`

- [ ] **Step 1: Replace the compact training-only `job.submit` form draft with a typed task-kind-driven draft**
- [ ] **Step 2: Serialize task-kind defaults so manual control always emits a valid unified payload**
- [ ] **Step 3: Update manual preview and ledger summaries to show task kind, lifecycle, ports, and restartability**
- [ ] **Step 4: Remove training-only copy from the cluster job ledger and reflect richer task metadata**
- [ ] **Step 5: Run focused frontend tests green**
Run: `cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm test -- src\lib\controlCapabilityModels.test.js src\lib\clusterConsoleModels.test.js"`
Expected: PASS.

### Task 6: Add Rule-Based Agent Submit Planning

**Files:**
- Modify: `backend/app/services/goal_runtime/control_heuristic_support.py`
- Modify: `backend/app/services/goal_runtime/control_heuristics.py`
- Modify: `backend/app/services/goal_runtime/planner.py`

- [ ] **Step 1: Add a focused `submit_job` heuristic extractor for training, inference service, interactive session, batch compute, and maintenance intents**
- [ ] **Step 2: Keep the emitted arguments aligned with the unified `job.submit` payload shape**
- [ ] **Step 3: Ensure planner fallback continues to map `submit_job` onto `job.submit` without new branching**
- [ ] **Step 4: Run focused Agent runtime tests green**
Run: `timeout 60s cmd.exe /c "E:\Code\AI-DataCenter\.venv\Scripts\python.exe -m pytest tests\test_goal_runtime_planner.py tests\test_goal_runtime_capabilities.py -q"`
Expected: PASS.

### Task 7: Verify The Slice On Windows

**Files:**
- Verify only

- [ ] **Step 1: Run backend regression with 60s timeout**
Run: `timeout 60s cmd.exe /c "E:\Code\AI-DataCenter\.venv\Scripts\python.exe -m pytest tests\test_cluster_job_api.py tests\test_cluster_scheduler_core.py tests\test_node_runtime_api.py tests\test_goal_runtime_capabilities.py tests\test_goal_runtime_planner.py -q"`
Expected: PASS.
- [ ] **Step 2: Run frontend targeted regression**
Run: `cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm test -- src\lib\controlCapabilityModels.test.js src\lib\clusterConsoleModels.test.js"`
Expected: PASS.
- [ ] **Step 3: Run frontend production build**
Run: `cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm run build"`
Expected: Build succeeds without new task-model-related errors.
- [ ] **Step 4: Inspect final workspace diff**
Run: `git status --short`
Expected: Only the planned backend, server-agent, frontend, and test files are modified.

## Self-Review

- Spec coverage: the plan covers the four approved design sections in order: unified task model, scheduler semantics, shared manual/Agent submit path, and first-phase runtime/HTTP agent boundary.
- Placeholder scan: no `TBD`, `TODO`, or deferred “implement later” steps remain.
- Type consistency: all tasks use the same field names: `task_kind`, `lifecycle_kind`, `service_ports`, `checkpoint_policy`, `runtime_profile`.
