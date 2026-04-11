# Checkpoint-Aware Preemption And Restore Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `preempt_then_place` from ledger-only state transitions into a real checkpoint-aware reclaim and restore workflow that shares the same job-control foundation as manual and Agent actions.

**Architecture:** Keep `ClusterControlPlaneService -> control_plane_job_actions -> ExecutionOrchestrator -> HTTPAgentProcessBackend -> server-agent runtime` as the single execution chain. Reconcile should request checkpoint on reclaimable victims, runtime feedback should release checkpoint-ready victims, and the normal placement path should be able to restore from a ready checkpoint instead of always launching from scratch.

**Tech Stack:** FastAPI, Python, `aiosqlite`, `pytest`, Vue capability layer already wired to backend control-plane methods, Windows-first verification via `cmd.exe`.

---

### Task 1: Red Tests For Checkpoint-Aware Preemption

**Files:**
- Modify: `tests/test_cluster_scheduler_core.py`

- [ ] Add a failing test proving `preempt_then_place` on an `app_managed` victim requests runtime checkpoint instead of only flipping ledger state.
- [ ] Add a failing test proving `checkpoint_ready` on a `preempting` victim releases its reservation/allocation and moves it into a restoreable state.
- [ ] Add a failing test proving a job with a ready checkpoint uses restore dispatch instead of fresh launch when reconcile places it again.
- [ ] Run: `timeout 60s cmd.exe /c "cd /d E:\Code\AI-DataCenter && .venv\Scripts\python.exe -m pytest tests\test_cluster_scheduler_core.py -q"`
- [ ] Confirm the new tests fail for the expected missing behaviors before implementation.

### Task 2: Implement Shared Checkpoint-Aware Reclaim Helpers

**Files:**
- Create: `backend/app/services/cluster_control/reclaim_runtime.py`
- Modify: `backend/app/services/cluster_control/control_plane_job_actions.py`
- Modify: `backend/app/services/cluster_control/reconcile_execution.py`
- Modify: `backend/app/services/cluster_control/runtime_feedback.py`

- [ ] Add focused helpers to classify checkpoint-capable reclaim victims and build/update shared checkpoint records.
- [ ] Make `preempt_then_place` request runtime checkpoint through the same orchestrator backend used by manual `job.checkpoint`.
- [ ] Keep victim jobs in explicit reclaim states instead of silently releasing before checkpoint completes.
- [ ] When runtime feedback sees `checkpoint_ready` for reclaiming jobs, release allocation/reservation through the same shared release helpers and move the job into a restoreable queue state.

### Task 3: Implement Restore Dispatch On Normal Placement Path

**Files:**
- Modify: `backend/app/services/cluster_control/execution_orchestrator.py`
- Modify: `backend/app/services/cluster_control/reconcile_runtime.py`
- Modify: `backend/app/services/cluster_control/reconcile_execution.py`
- Modify: `backend/app/services/cluster_control/control_plane.py`

- [ ] Add orchestrator support for “create reservation + restore runtime job + persist allocation” so restore dispatch is first-class rather than a one-off manual path.
- [ ] Reuse ready checkpoint history when a checkpointed job re-enters reconcile and gets a `place` plan.
- [ ] Ensure manual and Agent job restore continue to flow through `ClusterControlPlaneService` and the same underlying orchestrator/runtime methods.

### Task 4: Verification

**Files:**
- Modify: `tests/test_cluster_scheduler_core.py`
- Modify: `tests/test_cluster_checkpoint_history.py`
- Modify: `tests/test_goal_runtime_cluster_capabilities.py` only if behavior surface changes

- [ ] Run: `timeout 60s cmd.exe /c "cd /d E:\Code\AI-DataCenter && .venv\Scripts\python.exe -m pytest tests\test_cluster_scheduler_core.py tests\test_cluster_checkpoint_history.py tests\test_cluster_job_api.py tests\test_goal_runtime_cluster_capabilities.py tests\test_goal_runtime_planner.py tests\test_node_runtime_api.py -q"`
- [ ] Run: `cmd.exe /c "cd /d E:\Code\AI-DataCenter && .venv\Scripts\python.exe -m compileall backend\app"`
- [ ] Confirm the new reclaim/restore path passes without introducing a second manual-vs-Agent control implementation.
