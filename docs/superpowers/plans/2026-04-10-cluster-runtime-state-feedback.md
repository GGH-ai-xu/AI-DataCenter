# Cluster Runtime State Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first runtime-lifecycle closure slice: sync node runtime states back into the control plane, release resources on terminal jobs, and make running-job cancel use the real execution backend.

**Architecture:** Keep `cluster_control` as the single source of truth. Extend the node agent to expose runtime job snapshots and terminate-by-handle, teach the backend execution backend to read and terminate runtime jobs, then add a pull-based runtime reconciliation pass before queue dispatch so terminal jobs become `succeeded / failed / canceled` and their allocations/reservations are released.

**Tech Stack:** FastAPI, Python dataclasses, in-memory node runtime store, Vue 3, Python `pytest`/`unittest`, Node `node:test`.

---

### Task 1: Add Red Tests For Node Runtime State APIs

**Files:**
- Modify: `tests/test_node_runtime_api.py`

- [ ] **Step 1: Add failing test for listing runtime jobs with terminal states**
- [ ] **Step 2: Add failing test for terminating a runtime job by handle**
- [ ] **Step 3: Run node runtime tests red**

### Task 2: Implement Node Runtime Snapshot And Termination

**Files:**
- Modify: `server-agent/runtime_store.py`
- Modify: `server-agent/job_runtime.py`
- Modify: `server-agent/main.py`

- [ ] **Step 1: Persist runtime job terminal metadata (`exit_code`, `finished_at`, `last_error`)**
- [ ] **Step 2: Expose `GET /api/runtime/jobs`**
- [ ] **Step 3: Expose `POST /api/runtime/jobs/{job_handle}/terminate`**
- [ ] **Step 4: Run node runtime tests green**

### Task 3: Add Backend Runtime Query And Terminate Support

**Files:**
- Modify: `backend/app/services/cluster_control/execution_backend.py`
- Modify: `backend/app/services/cluster_control/execution_orchestrator.py`

- [ ] **Step 1: Add `list_jobs()` and `terminate_job()` to HTTP runtime backend**
- [ ] **Step 2: Add orchestrator helpers for node runtime snapshot and terminate**
- [ ] **Step 3: Keep unsupported backends explicit**
- [ ] **Step 4: Run focused backend tests if added**

### Task 4: Add Runtime Reconciliation To Cluster Control Plane

**Files:**
- Modify: `tests/test_cluster_scheduler_core.py`
- Modify: `backend/app/services/cluster_control/control_plane.py`
- Create: `backend/app/services/cluster_control/runtime_feedback.py`

- [ ] **Step 1: Add failing tests for terminal runtime sync and resource release**
- [ ] **Step 2: Add failing test for canceling a running job through the backend**
- [ ] **Step 3: Implement pull-based runtime reconciliation helpers**
- [ ] **Step 4: Make `reconcile_and_dispatch()` sync terminal jobs before dispatching queue work**
- [ ] **Step 5: Make `cancel_job()` terminate running jobs by `runtime_job_handle`**
- [ ] **Step 6: Run backend tests green**

### Task 5: Surface Terminal States In Cluster Console

**Files:**
- Modify: `frontend/src/components/cluster/ClusterJobLedger.vue`
- Modify: `frontend/src/lib/clusterConsoleModels.test.js`

- [ ] **Step 1: Add failing frontend expectation for succeeded/canceled display semantics if needed**
- [ ] **Step 2: Update job ledger badge styling for terminal states**
- [ ] **Step 3: Run focused frontend tests green**

### Task 6: Verify On Windows

**Files:**
- Verify only

- [ ] **Step 1: Run `E:\\Code\\AI-DataCenter\\.venv\\Scripts\\python.exe -m pytest tests\\test_node_runtime_api.py tests\\test_cluster_scheduler_core.py tests\\test_cluster_job_api.py -q`**
- [ ] **Step 2: Run `cd E:\\Code\\AI-DataCenter\\frontend && npm test -- src\\lib\\clusterConsoleModels.test.js`**
- [ ] **Step 3: Run `cd E:\\Code\\AI-DataCenter\\frontend && npm run build`**
- [ ] **Step 4: Inspect `git status --short`**
