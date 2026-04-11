# Cluster Scheduling Phase 2 Planning And Admission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first planning-focused Phase 2 slice: queue admission, wait/reject reasons, `job.plan` / `reschedule.plan` capabilities, and cluster console visibility into those scheduler outcomes.

**Architecture:** Keep the existing `cluster_control` package as the single source of scheduling truth. Extend queue and job persistence with admission/plan metadata, teach `ClusterSchedulerCore` to evaluate queue state and concurrency before placement, expose plan-only control-plane methods for runtime capabilities, and map the resulting plan reason fields into the cluster queue console.

**Tech Stack:** FastAPI, Python dataclasses, `aiosqlite`, Vue 3, Axios, Python `pytest`, Node `node:test`.

---

### Task 1: Add Red Tests For Admission And Plan Capabilities

**Files:**
- Modify: `tests/test_cluster_scheduler_core.py`
- Modify: `tests/test_goal_runtime_cluster_capabilities.py`
- Modify: `tests/test_goal_runtime_planner.py`
- Modify: `frontend/src/lib/clusterConsoleModels.test.js`

- [ ] **Step 1: Add failing scheduler tests for inactive queues and concurrency waits**
- [ ] **Step 2: Add failing capability/planner tests for `job.plan` and `reschedule.plan`**
- [ ] **Step 3: Add failing frontend model test for queue wait reason summaries**
- [ ] **Step 4: Run red tests**

### Task 2: Implement Queue Admission And Plan Metadata In Cluster Control

**Files:**
- Modify: `backend/app/services/cluster_control/models.py`
- Modify: `backend/app/services/cluster_control/sqlite_support.py`
- Modify: `backend/app/services/data_store.py`
- Modify: `backend/app/services/cluster_control/scheduler_core.py`
- Modify: `backend/app/services/cluster_control/control_plane.py`

- [ ] **Step 1: Persist queue `max_concurrency` and job `last_plan_type/last_plan_reason`**
- [ ] **Step 2: Extend scheduler to evaluate queue state and concurrency before placement**
- [ ] **Step 3: Add `plan_job` and `plan_reschedule` methods to the control plane**
- [ ] **Step 4: Make submit flow persist pending/rejected plan outcomes**
- [ ] **Step 5: Run backend tests to green**

### Task 3: Register Planning Capabilities And Heuristic Mappings

**Files:**
- Create: `backend/app/services/goal_runtime/cluster_planning_capabilities.py`
- Modify: `backend/app/services/goal_runtime/platform_capabilities.py`
- Modify: `backend/app/services/goal_runtime/planner.py`
- Modify: `backend/app/services/goal_runtime/control_heuristics.py`

- [ ] **Step 1: Register `job.plan` and `reschedule.plan` as non-mutating cluster capabilities**
- [ ] **Step 2: Map planner actions to the new capabilities**
- [ ] **Step 3: Add simple heuristic extraction for planning and rescheduling requests**
- [ ] **Step 4: Run runtime tests to green**

### Task 4: Surface Scheduler Outcomes In Cluster Console

**Files:**
- Modify: `frontend/src/lib/clusterConsoleModels.js`
- Modify: `frontend/src/components/cluster/ClusterQueueBoard.vue`
- Modify: `frontend/src/views/ClusterJobs.vue`

- [ ] **Step 1: Map queue concurrency and job wait reasons into the view model**
- [ ] **Step 2: Show queue wait reason summaries in the queue board**
- [ ] **Step 3: Refresh the cluster console without changing the overall page structure**
- [ ] **Step 4: Run frontend tests to green**

### Task 5: Verify The Slice End To End

**Files:**
- Verify only

- [ ] **Step 1: Run focused backend regression**
- [ ] **Step 2: Run focused frontend regression**
- [ ] **Step 3: Run frontend production build**
- [ ] **Step 4: Inspect `git status --short` for unrelated fallout**
