# Cluster Reconcile Controller Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first automatic reconcile-control slice: a background cluster reconcile loop with health-aware skip behavior, shared manual/automatic entrypoints, and cluster console visibility into controller state.

**Architecture:** Introduce a dedicated `ClusterReconcileController` service instead of embedding loop logic in `main.py`. The controller owns enabled/interval state, executes `reconcile_and_dispatch()` through injected loaders, records last summaries and skip reasons, and is exposed through small cluster APIs that the cluster console can read and update.

**Tech Stack:** FastAPI, asyncio, Vue 3, Axios, Python `pytest`/`unittest`, Node `node:test`.

---

### Task 1: Add Red Tests For The Controller Service

**Files:**
- Create: `tests/test_cluster_reconcile_controller.py`

- [ ] **Step 1: Add failing test for health-aware skip**
- [ ] **Step 2: Add failing test for background loop ticking when enabled**
- [ ] **Step 3: Run controller tests red**

### Task 2: Implement ClusterReconcileController

**Files:**
- Create: `backend/app/services/cluster_control/reconcile_controller.py`

- [ ] **Step 1: Implement controller state snapshot and configure**
- [ ] **Step 2: Implement `run_once(trigger=...)` with runtime-status skip**
- [ ] **Step 3: Implement `start()` / `shutdown()` background loop**
- [ ] **Step 4: Run controller tests green**

### Task 3: Wire Controller Into App Startup And Cluster APIs

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/cluster_jobs.py`
- Modify: `backend/app/models/schemas.py`
- Modify: `tests/test_cluster_job_api.py`

- [ ] **Step 1: Add failing API tests for controller status/configure routes**
- [ ] **Step 2: Add controller to `app_state` and lifespan**
- [ ] **Step 3: Make manual reconcile route call controller `run_once()`**
- [ ] **Step 4: Add `GET/POST /api/cluster/controller`**
- [ ] **Step 5: Run API tests green**

### Task 4: Surface Controller State In Cluster Console

**Files:**
- Modify: `frontend/src/services/api.js`
- Modify: `frontend/src/lib/clusterConsoleModels.js`
- Modify: `frontend/src/lib/clusterConsoleModels.test.js`
- Modify: `frontend/src/components/cluster/ClusterConsoleToolbar.vue`
- Modify: `frontend/src/views/ClusterJobs.vue`

- [ ] **Step 1: Add failing frontend test for controller status mapping**
- [ ] **Step 2: Load controller status during cluster console refresh**
- [ ] **Step 3: Add toolbar status text and enable/disable action**
- [ ] **Step 4: Run frontend tests green**

### Task 5: Verify On Windows

**Files:**
- Verify only

- [ ] **Step 1: Run `E:\\Code\\AI-DataCenter\\.venv\\Scripts\\python.exe -m pytest tests\\test_cluster_reconcile_controller.py tests\\test_cluster_job_api.py -q`**
- [ ] **Step 2: Run `cd E:\\Code\\AI-DataCenter && E:\\Code\\AI-DataCenter\\.venv\\Scripts\\python.exe -m pytest tests\\test_node_runtime_api.py tests\\test_cluster_scheduler_core.py tests\\test_cluster_job_api.py tests\\test_cluster_reconcile_controller.py -q`**
- [ ] **Step 3: Run `cd E:\\Code\\AI-DataCenter\\frontend && npm test -- src\\lib\\clusterConsoleModels.test.js`**
- [ ] **Step 4: Run `cd E:\\Code\\AI-DataCenter\\frontend && npm run build`**
- [ ] **Step 5: Inspect `git status --short`**
