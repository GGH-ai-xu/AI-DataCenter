# Cluster Preemption, Requeue, And Reconcile Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the current cluster job control path from “initial placement only” into a multi-wave reconcile system that can make running jobs yield, release allocations, requeue victims, and then advance higher-priority jobs.

**Architecture:** Keep the current `ClusterReconcileController -> ClusterControlPlaneService -> ClusterSchedulerCore -> ExecutionOrchestrator -> HTTPAgentProcessBackend -> server-agent job_runtime` chain. Add an explicit scheduling decision model, a victim selector, reconcile-wave execution helpers, lifecycle-aware control semantics, and shared manual/Agent capabilities so automatic and manual control operate on the same job and allocation states.

**Tech Stack:** FastAPI, Python dataclasses, `aiosqlite`, Vue 3, Node `node:test`, `pytest`, server-agent FastAPI runtime.

---

## Planned File Map

- `backend/app/services/cluster_control/models.py`
  - Extend `PlacementPlan` into a richer scheduling decision carrier without introducing a second top-level planner type.
- `backend/app/services/cluster_control/preemption_selector.py`
  - New focused helper for selecting victim jobs and allocations from active cluster state.
- `backend/app/services/cluster_control/scheduler_core.py`
  - Produce `place / wait / reject / preempt_then_place / release_then_place / requeue / hold` decisions.
- `backend/app/services/cluster_control/control_plane.py`
  - Add lifecycle-aware job control methods and drive reconcile decisions through the orchestrator.
- `backend/app/services/cluster_control/reconcile_runtime.py`
  - Build and persist reconcile-wave actions, including victim state transitions and delayed follow-up placement.
- `backend/app/services/cluster_control/runtime_feedback.py`
  - Convert runtime terminal and releasing states into cluster job/allocation state transitions.
- `backend/app/services/cluster_control/job_projection.py`
  - Project richer job/allocation states and victim progress into cluster job responses.
- `backend/app/services/goal_runtime/cluster_execution_capabilities.py`
  - Add manual and Agent-facing cluster execution capabilities such as `job.requeue`.
- `backend/app/services/goal_runtime/platform_capabilities.py`
  - Wire the new job control capabilities into the shared registry without bloating old capability handlers.
- `backend/app/services/goal_runtime/planner.py`
  - Map new `requeue_job` and `preempt_job` planner actions onto the shared capability surface.
- `backend/app/services/goal_runtime/control_heuristic_support.py`
  - Add basic extraction helpers for `requeue job` / `preempt job`.
- `backend/app/services/goal_runtime/control_heuristics.py`
  - Include the new cluster-execution heuristics in fallback planning.
- `frontend/src/lib/controlCapabilityForms.js`
  - Add typed manual forms for `job.requeue` and `job.preempt`.
- `frontend/src/lib/controlCapabilityModels.js`
  - Summarize new job control actions cleanly in the command ledger.
- `frontend/src/lib/clusterConsoleModels.js`
  - Expose `preempting / preempted / requeue_requested / releasing` and victim-follow-up summaries to the cluster UI.
- `frontend/src/components/cluster/ClusterJobLedger.vue`
  - Show richer lifecycle states and manual job-control actions.
- `frontend/src/components/cluster/ClusterAllocationPanel.vue`
  - Show releasing/orphaned allocation states so operators can see real reclaim progress.
- `frontend/src/components/governance/CapabilityCommandDrawer.vue`
  - Render the new manual control forms through the shared typed form system.
- `tests/test_cluster_control_models.py`
  - Cover richer scheduling decision fields and immutable defaults.
- `tests/test_cluster_scheduler_core.py`
  - Cover victim selection, preemption decisions, lifecycle restrictions, and requeue decisions.
- `tests/test_cluster_reconcile_controller.py`
  - Cover multi-wave reconcile progression and skip/retry behavior.
- `tests/test_cluster_job_api.py`
  - Cover richer job/allocation states surfacing through list/detail routes.
- `tests/test_goal_runtime_cluster_capabilities.py`
  - Cover new cluster execution capabilities and planner mappings.
- `tests/test_goal_runtime_planner.py`
  - Cover rule extraction for `requeue_job` and `preempt_job`.
- `frontend/src/lib/controlCapabilityModels.test.js`
  - Cover new manual capability forms and ledger summaries.
- `frontend/src/lib/clusterConsoleModels.test.js`
  - Cover richer state projection for jobs and allocations.

### Task 1: Write Red Tests For Preemption, Requeue, And Reconcile Waves

**Files:**
- Modify: `tests/test_cluster_control_models.py`
- Modify: `tests/test_cluster_scheduler_core.py`
- Modify: `tests/test_cluster_reconcile_controller.py`
- Modify: `tests/test_cluster_job_api.py`
- Modify: `tests/test_goal_runtime_cluster_capabilities.py`
- Modify: `tests/test_goal_runtime_planner.py`
- Modify: `frontend/src/lib/controlCapabilityModels.test.js`
- Modify: `frontend/src/lib/clusterConsoleModels.test.js`

- [ ] **Step 1: Add failing model tests for richer scheduling decisions**

```python
def test_placement_plan_carries_victim_and_action_metadata():
    plan = PlacementPlan(
        job_id="job-target",
        plan_type="preempt_then_place",
        selected_node="node-a",
        selected_devices=("gpu-0",),
        score_breakdown={"fit": 1.0},
        victim_job_ids=("job-low",),
        victim_allocation_ids=("alloc-low",),
        followup_job_ids=("job-target",),
        required_actions=(
            {"action": "cancel_job", "job_id": "job-low"},
            {"action": "release_allocation", "allocation_id": "alloc-low"},
        ),
    )

    assert plan.victim_job_ids == ("job-low",)
    assert plan.required_actions[0]["action"] == "cancel_job"
```

- [ ] **Step 2: Add failing scheduler tests for `preempt_then_place` and `requeue`**

```python
def test_high_priority_batch_can_preempt_low_priority_batch():
    plan = scheduler.plan_job(
        high_priority_job,
        nodes=[node_a],
        jobs=[high_priority_job_item, low_priority_job_item],
        allocations=[low_priority_allocation],
        governance_rules={"alice": {"allow_preempt": True}},
    )

    assert plan.plan_type == "preempt_then_place"
    assert plan.victim_job_ids == ("job-low",)
```

```python
def test_service_job_is_not_selected_as_default_victim():
    plan = scheduler.plan_job(
        target_batch_job,
        nodes=[node_a],
        jobs=[target_item, service_item],
        allocations=[service_allocation],
        governance_rules={"svc-user": {"allow_preempt": True}},
    )

    assert plan.plan_type == "wait"
```

- [ ] **Step 3: Add failing reconcile tests for multi-wave progression**

```python
async def test_reconcile_wave_marks_victim_preempting_before_followup_dispatch():
    summary = await service.reconcile_and_dispatch(nodes=[node_a])

    assert store.jobs["job-low"]["status"] == "preempting"
    assert store.jobs["job-target"]["status"] == "pending"
    assert summary["jobs"][0]["status"] == "preempting"
```

- [ ] **Step 4: Add failing capability and planner tests for `job.requeue` / `job.preempt`**

```python
def test_cluster_job_control_capabilities_are_registered():
    registry = build_platform_capability_registry(_build_state())

    assert registry.get("job.requeue").definition.domain == "jobs"
    assert registry.get("job.preempt").definition.domain == "jobs"
```

```python
def test_planner_maps_requeue_job_action_to_capability():
    plan = build_initial_plan(goal_spec, registry)
    assert plan.steps[1].capability_name == "job.requeue"
```

- [ ] **Step 5: Add failing frontend projection and manual-form tests**

```javascript
test('buildCapabilityFormDraft exposes job.requeue and job.preempt forms', () => {
  assert.equal(buildCapabilityFormDraft('job.requeue').job_id, '')
  assert.equal(buildCapabilityFormDraft('job.preempt').job_id, '')
})
```

```javascript
test('buildClusterConsoleModel projects preempting and releasing states', () => {
  const model = buildClusterConsoleModel({
    jobs: [{ job_id: 'job-low', status: 'preempting' }],
    allocations: [{ allocation_id: 'alloc-low', job_id: 'job-low', node_id: 'node-a', status: 'releasing' }],
  })

  assert.equal(model.jobs[0].status, 'preempting')
  assert.equal(model.allocationsByNode[0].allocations[0].status, 'releasing')
})
```

- [ ] **Step 6: Run focused backend red tests**
Run: `timeout 60s cmd.exe /c "E:\Code\AI-DataCenter\.venv\Scripts\python.exe -m pytest tests\test_cluster_control_models.py tests\test_cluster_scheduler_core.py tests\test_cluster_reconcile_controller.py tests\test_cluster_job_api.py tests\test_goal_runtime_cluster_capabilities.py tests\test_goal_runtime_planner.py -q"`
Expected: FAIL in the new decision-model, preemption, reconcile-wave, and capability assertions.

- [ ] **Step 7: Run focused frontend red tests**
Run: `cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm test -- src\lib\controlCapabilityModels.test.js src\lib\clusterConsoleModels.test.js"`
Expected: FAIL in the new manual-form and richer state-projection assertions.

### Task 2: Expand The Scheduling Decision And Cluster State Model

**Files:**
- Modify: `backend/app/services/cluster_control/models.py`
- Modify: `backend/app/services/cluster_control/job_projection.py`
- Modify: `tests/test_cluster_control_models.py`

- [ ] **Step 1: Extend `PlacementPlan` with victim, follow-up, and action metadata**

```python
@dataclass(frozen=True)
class PlacementPlan:
    job_id: str
    plan_type: str
    selected_node: str
    selected_devices: tuple[str, ...]
    score_breakdown: Mapping[str, float]
    execution_backend: str = ""
    alternatives: tuple[str, ...] = ()
    reason: str = ""
    victim_job_ids: tuple[str, ...] = ()
    victim_allocation_ids: tuple[str, ...] = ()
    followup_job_ids: tuple[str, ...] = ()
    required_actions: tuple[Mapping[str, Any], ...] = ()
```

- [ ] **Step 2: Keep the decision carrier immutable and normalize nested action payloads**

```python
def _freeze_actions(value: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]] | None):
    return tuple(MappingProxyType(dict(item)) for item in (value or ()))
```

- [ ] **Step 3: Project richer job and allocation states for UI/API consumers**

```python
def attach_runtime_handles_to_jobs(jobs, allocations):
    releasing = {str(item.get("job_id") or "") for item in allocations if str(item.get("status") or "") == "releasing"}
    return [
        {
            **item,
            "runtime_job_handle": handles.get(str(item.get("job_id") or ""), ""),
            "has_releasing_allocation": str(item.get("job_id") or "") in releasing,
        }
        for item in jobs
    ]
```

- [ ] **Step 4: Run focused model tests green**
Run: `timeout 60s cmd.exe /c "E:\Code\AI-DataCenter\.venv\Scripts\python.exe -m pytest tests\test_cluster_control_models.py -q"`
Expected: PASS.

- [ ] **Step 5: Commit the decision-model slice**

```bash
git add backend/app/services/cluster_control/models.py backend/app/services/cluster_control/job_projection.py tests/test_cluster_control_models.py
git commit -m "feat: add richer cluster scheduling decision model"
```

### Task 3: Add Victim Selection And Scheduler Decisions

**Files:**
- Create: `backend/app/services/cluster_control/preemption_selector.py`
- Modify: `backend/app/services/cluster_control/scheduler_core.py`
- Modify: `backend/app/services/cluster_control/control_plane.py`
- Modify: `backend/app/services/cluster_control/reconcile_runtime.py`
- Modify: `tests/test_cluster_scheduler_core.py`

- [ ] **Step 1: Implement a focused victim selector module**

```python
def select_victims(*, target_job, jobs, allocations, governance_rules):
    candidates = [
        item for item in jobs
        if _job_can_yield(item, allocations, governance_rules)
    ]
    ranked = sorted(candidates, key=lambda item: _victim_sort_key(item, target_job))
    return ranked[:1]
```

- [ ] **Step 2: Teach `ClusterSchedulerCore` to return execution-type decisions**

```python
if direct_candidates:
    return PlacementPlan(..., plan_type="place")
victims = select_victims(...)
if victims:
    return PlacementPlan(
        job_id=job.job_id,
        plan_type="preempt_then_place",
        selected_node=victim_node_id,
        selected_devices=tuple(victim_devices),
        victim_job_ids=(victim_job_id,),
        victim_allocation_ids=(victim_allocation_id,),
        followup_job_ids=(job.job_id,),
        required_actions=(
            {"action": "cancel_job", "job_id": victim_job_id},
            {"action": "release_allocation", "allocation_id": victim_allocation_id},
        ),
        reason="higher-priority batch requires reclaiming active allocation",
    )
return PlacementPlan(..., plan_type="wait")
```

- [ ] **Step 3: Thread governance rules and current active allocations into planning**

```python
return self.scheduler.plan_job(
    job_record,
    nodes,
    queue=await load_queue(...),
    jobs=jobs,
    allocations=build_planning_allocations(...),
    governance_rules=await self.store.get_user_governance_rules(),
)
```

- [ ] **Step 4: Run focused scheduler tests green**
Run: `timeout 60s cmd.exe /c "E:\Code\AI-DataCenter\.venv\Scripts\python.exe -m pytest tests\test_cluster_scheduler_core.py -q"`
Expected: PASS.

- [ ] **Step 5: Commit the scheduler decision slice**

```bash
git add backend/app/services/cluster_control/preemption_selector.py backend/app/services/cluster_control/scheduler_core.py backend/app/services/cluster_control/control_plane.py backend/app/services/cluster_control/reconcile_runtime.py tests/test_cluster_scheduler_core.py
git commit -m "feat: add victim selection and preemption decisions"
```

### Task 4: Implement Multi-Wave Reconcile Execution And Runtime Feedback

**Files:**
- Create: `backend/app/services/cluster_control/reconcile_execution.py`
- Modify: `backend/app/services/cluster_control/control_plane.py`
- Modify: `backend/app/services/cluster_control/reconcile_runtime.py`
- Modify: `backend/app/services/cluster_control/runtime_feedback.py`
- Modify: `backend/app/services/cluster_control/reconcile_controller.py`
- Modify: `tests/test_cluster_reconcile_controller.py`
- Modify: `tests/test_cluster_job_api.py`

- [ ] **Step 1: Move reconcile-wave action execution into a focused helper**

```python
async def execute_reconcile_decision(store, orchestrator, decision, nodes):
    if decision.plan_type == "preempt_then_place":
        await _mark_victims_preempting(store, decision)
        return {"status": "preempting", "job_id": decision.job_id}
    if decision.plan_type == "place":
        await dispatch_placement_plan(...)
        return {"status": "running", "job_id": decision.job_id}
    return {"status": "pending", "job_id": decision.job_id}
```

- [ ] **Step 2: Update runtime feedback to release resources and unblock follow-up jobs**

```python
if runtime_job.get("state") == "canceled":
    await store.update_cluster_job_state(job_id, "preempted", ...)
    await release_runtime_resources(store, allocation)
```

- [ ] **Step 3: Keep reconcile idempotent across waves**

```python
if current_status in {"preempting", "requeue_requested"}:
    return PlacementPlan(job_id=job_id, plan_type="hold", selected_node="", selected_devices=(), score_breakdown={"fit": 0.0}, reason="waiting for victim release")
```

- [ ] **Step 4: Run focused reconcile and API tests green**
Run: `timeout 60s cmd.exe /c "E:\Code\AI-DataCenter\.venv\Scripts\python.exe -m pytest tests\test_cluster_reconcile_controller.py tests\test_cluster_job_api.py -q"`
Expected: PASS.

- [ ] **Step 5: Commit the reconcile-wave slice**

```bash
git add backend/app/services/cluster_control/reconcile_execution.py backend/app/services/cluster_control/control_plane.py backend/app/services/cluster_control/reconcile_runtime.py backend/app/services/cluster_control/runtime_feedback.py backend/app/services/cluster_control/reconcile_controller.py tests/test_cluster_reconcile_controller.py tests/test_cluster_job_api.py
git commit -m "feat: add multi-wave reconcile execution"
```

### Task 5: Enforce Lifecycle-Aware Job Control And Shared Capabilities

**Files:**
- Modify: `backend/app/services/cluster_control/control_plane.py`
- Modify: `backend/app/services/goal_runtime/cluster_execution_capabilities.py`
- Modify: `backend/app/services/goal_runtime/platform_capabilities.py`
- Modify: `backend/app/services/goal_runtime/planner.py`
- Modify: `backend/app/services/goal_runtime/control_heuristic_support.py`
- Modify: `backend/app/services/goal_runtime/control_heuristics.py`
- Modify: `tests/test_goal_runtime_cluster_capabilities.py`
- Modify: `tests/test_goal_runtime_planner.py`

- [ ] **Step 1: Add lifecycle-aware job control methods**

```python
async def requeue_job(self, job_id: str) -> dict:
    job = await self.store.get_cluster_job(job_id)
    if str(job.get("lifecycle_kind") or "") == "service":
        raise ValueError("service jobs do not support requeue")
    await self.store.update_cluster_job_state(job_id, "requeue_requested", execution_backend="")
    await self.store.update_cluster_allocations_for_job(job_id, "releasing")
    return await self.store.get_cluster_job(job_id)
```

- [ ] **Step 2: Register `job.requeue` and `job.preempt` in the shared capability registry**

```python
registry.register(
    CapabilityDefinition("job.requeue", "jobs", "runtime_action", False, supported_providers, manual_control=manual_factory(...)),
    handler=requeue_job,
)
```

- [ ] **Step 3: Map planner actions and fallback heuristics onto the new capability surface**

```python
ACTION_CAPABILITY_MAP.update({
    "requeue_job": "job.requeue",
    "preempt_job": "job.preempt",
})
```

```python
if any(word in text for word in ("重排作业", "重新排队", "requeue")):
    return [{"action": "requeue_job", "target": {"job_id": job_id}, "reason": f"根据用户指令将作业 {job_id} 重新入队"}]
```

- [ ] **Step 4: Run focused capability and planner tests green**
Run: `timeout 60s cmd.exe /c "E:\Code\AI-DataCenter\.venv\Scripts\python.exe -m pytest tests\test_goal_runtime_cluster_capabilities.py tests\test_goal_runtime_planner.py -q"`
Expected: PASS.

- [ ] **Step 5: Commit the capability slice**

```bash
git add backend/app/services/cluster_control/control_plane.py backend/app/services/goal_runtime/cluster_execution_capabilities.py backend/app/services/goal_runtime/platform_capabilities.py backend/app/services/goal_runtime/planner.py backend/app/services/goal_runtime/control_heuristic_support.py backend/app/services/goal_runtime/control_heuristics.py tests/test_goal_runtime_cluster_capabilities.py tests/test_goal_runtime_planner.py
git commit -m "feat: add lifecycle-aware cluster job control capabilities"
```

### Task 6: Surface Reclaim Progress And Manual Actions In The Frontend

**Files:**
- Modify: `frontend/src/lib/controlCapabilityForms.js`
- Modify: `frontend/src/lib/controlCapabilityModels.js`
- Modify: `frontend/src/lib/clusterConsoleModels.js`
- Modify: `frontend/src/components/cluster/ClusterJobLedger.vue`
- Modify: `frontend/src/components/cluster/ClusterAllocationPanel.vue`
- Modify: `frontend/src/components/governance/CapabilityCommandDrawer.vue`
- Modify: `frontend/src/lib/controlCapabilityModels.test.js`
- Modify: `frontend/src/lib/clusterConsoleModels.test.js`

- [ ] **Step 1: Add typed manual forms for `job.requeue` and `job.preempt`**

```javascript
'job.requeue': {
  kind: 'job.requeue',
  fields: [field('job_id', '作业 ID', 'text', { cast: 'string', defaultValue: '' })],
},
'job.preempt': {
  kind: 'job.preempt',
  fields: [field('job_id', '作业 ID', 'text', { cast: 'string', defaultValue: '' })],
},
```

- [ ] **Step 2: Project richer cluster states into the UI model**

```javascript
function normalizeJob(job = {}) {
  return {
    ...baseJob,
    status: job.status || 'queued',
    canRequeue: ['running', 'paused', 'preempted'].includes(job.status || ''),
    awaitingRelease: Boolean(job.has_releasing_allocation),
  }
}
```

- [ ] **Step 3: Show releasing allocations and manual reclaim actions in the ledger**

```vue
<button v-if="job.canRequeue" type="button" @click="emitAction(job, 'requeue')">
  重新入队
</button>
```

```vue
<span v-if="allocation.status === 'releasing'" class="status-badge status-badge--warning">
  releasing
</span>
```

- [ ] **Step 4: Run focused frontend tests green**
Run: `cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm test -- src\lib\controlCapabilityModels.test.js src\lib\clusterConsoleModels.test.js"`
Expected: PASS.

- [ ] **Step 5: Commit the frontend slice**

```bash
git add frontend/src/lib/controlCapabilityForms.js frontend/src/lib/controlCapabilityModels.js frontend/src/lib/clusterConsoleModels.js frontend/src/components/cluster/ClusterJobLedger.vue frontend/src/components/cluster/ClusterAllocationPanel.vue frontend/src/components/governance/CapabilityCommandDrawer.vue frontend/src/lib/controlCapabilityModels.test.js frontend/src/lib/clusterConsoleModels.test.js
git commit -m "feat: surface cluster reclaim progress in console ui"
```

### Task 7: Run End-To-End Verification On Windows

**Files:**
- Verify only

- [ ] **Step 1: Run backend regression with a hard timeout**
Run: `timeout 60s cmd.exe /c "E:\Code\AI-DataCenter\.venv\Scripts\python.exe -m pytest tests\test_cluster_control_models.py tests\test_cluster_scheduler_core.py tests\test_cluster_reconcile_controller.py tests\test_cluster_job_api.py tests\test_goal_runtime_cluster_capabilities.py tests\test_goal_runtime_planner.py -q"`
Expected: PASS.

- [ ] **Step 2: Run node runtime regression to ensure cancel/release semantics still behave**
Run: `timeout 60s cmd.exe /c "E:\Code\AI-DataCenter\.venv\Scripts\python.exe -m pytest tests\test_node_runtime_api.py -q"`
Expected: PASS.

- [ ] **Step 3: Run focused frontend regression**
Run: `cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm test -- src\lib\controlCapabilityModels.test.js src\lib\clusterConsoleModels.test.js"`
Expected: PASS.

- [ ] **Step 4: Run frontend production build**
Run: `cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm run build"`
Expected: Build succeeds without new cluster-governance-related errors.

- [ ] **Step 5: Inspect final workspace diff**
Run: `git status --short`
Expected: Only the planned backend, frontend, server-agent, and test files are modified.

## Self-Review

- Spec coverage:
  - Section 5 decision model maps to Task 2 and Task 3.
  - Section 6 lifecycle control semantics maps to Task 5.
  - Section 7 victim selection maps to Task 3.
  - Section 8 multi-wave reconcile maps to Task 4.
  - Section 9 richer states maps to Task 2, Task 4, and Task 6.
  - Section 10 manual and Agent shared capability surface maps to Task 5 and Task 6.
- Placeholder scan:
  - No `TODO`, `TBD`, or deferred implementation markers remain.
  - Each task includes exact file paths, exact commands, and explicit expected outcomes.
- Type consistency:
  - Plan type names use `place / wait / reject / preempt_then_place / release_then_place / requeue / hold`.
  - Job actions use `job.requeue` and `job.preempt`.
  - Richer cluster states consistently use `preempting / preempted / requeue_requested / releasing`.
