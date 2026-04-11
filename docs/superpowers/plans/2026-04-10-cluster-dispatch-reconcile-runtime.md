# Cluster Dispatch Reconcile Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first execution-closure slice for cluster scheduling: reconcile queued jobs into real dispatch attempts, persist dispatch failures and reservation truth, and show those states in the cluster console.

**Architecture:** Keep `cluster_control` as the single truth. Extend SQLite-backed cluster job/allocation/reservation metadata, add a stateful `reconcile_and_dispatch()` path in the control plane, expose a shared `queue.reconcile` capability, and project dispatching/failed/runtime-handle data into the cluster UI.

**Tech Stack:** FastAPI, Python dataclasses, `aiosqlite`, Vue 3, Axios, Python `pytest`, Node `node:test`.

---

### Task 1: Add Red Tests For Reconcile Dispatch And Failure Persistence

**Files:**
- Modify: `tests/test_cluster_scheduler_core.py`
- Modify: `tests/test_cluster_job_api.py`
- Modify: `tests/test_goal_runtime_cluster_capabilities.py`
- Modify: `tests/test_goal_runtime_planner.py`
- Modify: `frontend/src/lib/clusterConsoleModels.test.js`

- [ ] **Step 1: Add failing control-plane tests for reconcile dispatch and dispatch failure**
- [ ] **Step 2: Add failing API test for cluster reconcile entry**
- [ ] **Step 3: Add failing capability/planner tests for `queue.reconcile`**
- [ ] **Step 4: Add failing frontend model test for failed/dispatching job summaries**
- [ ] **Step 5: Run red tests**

### Task 2: Implement Reservation Persistence And Dispatch Failure State

**Files:**
- Modify: `backend/app/services/cluster_control/sqlite_support.py`
- Modify: `backend/app/services/data_store.py`
- Modify: `backend/app/services/cluster_control/models.py`
- Modify: `backend/app/services/cluster_control/execution_orchestrator.py`

- [ ] **Step 1: Persist `cluster_jobs.last_error` and `cluster_allocations.runtime_job_handle`**
- [ ] **Step 2: Implement `cluster_reservations` create/get/list/update helpers**
- [ ] **Step 3: Make orchestrator store reservation truth and runtime handle**
- [ ] **Step 4: Keep dispatch failures explicit, no silent fallback**
- [ ] **Step 5: Run focused backend tests**

### Task 3: Add Stateful Reconcile Dispatch To Cluster Control Plane

**Files:**
- Modify: `backend/app/services/cluster_control/control_plane.py`
- Modify: `backend/app/api/cluster_jobs.py`
- Modify: `backend/app/models/schemas.py`

- [ ] **Step 1: Add `dispatching` / `failed` job transitions in control plane**
- [ ] **Step 2: Implement `reconcile_and_dispatch(nodes=...)` summary execution path**
- [ ] **Step 3: Expose `POST /api/cluster/reconcile`**
- [ ] **Step 4: Ensure dispatch errors persist `last_error` before surfacing**
- [ ] **Step 5: Run cluster API tests to green**

### Task 4: Register Shared Reconcile Capability And Planner Mapping

**Files:**
- Modify: `backend/app/services/goal_runtime/platform_capabilities.py`
- Modify: `backend/app/services/goal_runtime/planner.py`
- Modify: `backend/app/services/goal_runtime/control_heuristics.py`

- [ ] **Step 1: Register `queue.reconcile` capability**
- [ ] **Step 2: Add simple heuristic mapping for queue reconcile requests**
- [ ] **Step 3: Map planner action to capability**
- [ ] **Step 4: Run runtime tests to green**

### Task 5: Surface Dispatch Status In Cluster Console

**Files:**
- Modify: `frontend/src/lib/clusterConsoleModels.js`
- Modify: `frontend/src/components/cluster/ClusterQueueBoard.vue`
- Modify: `frontend/src/components/cluster/ClusterJobLedger.vue`
- Modify: `frontend/src/views/ClusterJobs.vue`

- [ ] **Step 1: Map `dispatching / failed / runtime_job_handle / last_error` into view model**
- [ ] **Step 2: Add reconcile action to cluster toolbar through shared capability chain**
- [ ] **Step 3: Show dispatch summaries and error details without changing page structure**
- [ ] **Step 4: Run frontend tests to green**

### Task 6: Verify The Slice On Windows

**Files:**
- Verify only

- [ ] **Step 1: Run focused backend regression**
- [ ] **Step 2: Run focused frontend regression**
- [ ] **Step 3: Run frontend production build**
- [ ] **Step 4: Inspect `git status --short` for unrelated fallout**
