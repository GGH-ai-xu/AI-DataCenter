# Cluster Scheduling Phase 2 Node And Allocation Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first cluster-scheduling Phase 2 control slice: drain/undrain nodes, release allocations, expose matching cluster/object capabilities, and make both the scheduler and cluster console respect those states.

**Architecture:** Extend the existing `cluster_control` control plane instead of creating a parallel path. Persist node drain state and allocation release state in SQLite, expose thin REST endpoints for cluster console refresh, and register `allocation.release` / `node.drain` / `node.undrain` in the shared goal-runtime capability registry so governance manual control and agent runtime use the same command chain.

**Tech Stack:** FastAPI, Python dataclasses, `aiosqlite`, Vue 3, Axios, Python `pytest`/`unittest`, Node `node:test`.

---

### Task 1: Write Backend Red Tests For Node And Allocation Control

**Files:**
- Modify: `tests/test_cluster_scheduler_core.py`
- Modify: `tests/test_cluster_job_api.py`
- Modify: `tests/test_goal_runtime_cluster_capabilities.py`

- [ ] **Step 1: Add failing scheduler/control-plane tests**

```python
def test_skips_drained_nodes_when_planning(self):
    plan = scheduler.plan_job(
        job,
        nodes=[
            {"node_id": "node-a", "schedulable": True, "drain_state": "drained", "gpu_free": 4},
            {"node_id": "node-b", "schedulable": True, "drain_state": "active", "gpu_free": 1},
        ],
    )
    self.assertEqual(plan.selected_node, "node-b")
```

- [ ] **Step 2: Add failing API tests for node drain and allocation release**

```python
response = self.client.post("/api/cluster/nodes/node-a/drain")
self.assertEqual(response.status_code, 200)

response = self.client.post("/api/cluster/allocations/alloc-job-1/release")
self.assertEqual(response.status_code, 200)
```

- [ ] **Step 3: Add failing capability/planner tests**

```python
self.assertEqual(registry.get("node.drain").definition.domain, "nodes")
self.assertEqual(registry.get("allocation.release").definition.domain, "allocations")
```

- [ ] **Step 4: Run red tests**

Run:

```bash
E:\Code\AI-DataCenter\.venv\Scripts\python.exe -m pytest tests/test_cluster_scheduler_core.py tests/test_cluster_job_api.py tests/test_goal_runtime_cluster_capabilities.py -q
```

Expected: FAIL on missing service methods, routes, and capability registrations.

### Task 2: Implement Persistence, Control-Plane Methods, And Cluster APIs

**Files:**
- Modify: `backend/app/services/cluster_control/sqlite_support.py`
- Modify: `backend/app/services/data_store.py`
- Modify: `backend/app/services/cluster_control/control_plane.py`
- Modify: `backend/app/services/cluster_control/scheduler_core.py`
- Modify: `backend/app/api/cluster_jobs.py`
- Modify: `backend/app/api/cluster_queues.py`
- Modify: `backend/app/models/schemas.py`

- [ ] **Step 1: Add SQLite helpers for node state and allocation release**

```python
async def upsert_node(db, payload): ...
async def list_nodes(db): ...
async def update_node_drain_state(db, node_id, drain_state): ...
async def release_allocation(db, allocation_id): ...
```

- [ ] **Step 2: Extend `DataStore` with node/allocation control helpers**

```python
async def upsert_cluster_node(self, payload): ...
async def list_cluster_nodes(self): ...
async def update_cluster_node_drain_state(self, node_id, drain_state): ...
async def release_cluster_allocation(self, allocation_id): ...
```

- [ ] **Step 3: Extend `ClusterControlPlaneService`**

```python
async def drain_node(self, node_id: str) -> dict: ...
async def undrain_node(self, node_id: str) -> dict: ...
async def release_allocation(self, allocation_id: str) -> dict: ...
```

- [ ] **Step 4: Make scheduler reject drained nodes**

```python
if str(node.get("drain_state") or "active") != "active":
    return False
```

- [ ] **Step 5: Expose thin cluster APIs**

```python
@router.post("/nodes/{node_id}/drain")
async def drain_cluster_node(node_id: str): ...

@router.post("/allocations/{allocation_id}/release")
async def release_cluster_allocation(allocation_id: str): ...
```

- [ ] **Step 6: Run backend tests to green**

Run:

```bash
E:\Code\AI-DataCenter\.venv\Scripts\python.exe -m pytest tests/test_cluster_scheduler_core.py tests/test_cluster_job_api.py -q
```

Expected: PASS.

### Task 3: Register Shared Capabilities And Planner Mappings

**Files:**
- Modify: `backend/app/services/goal_runtime/platform_capabilities.py`
- Modify: `backend/app/services/goal_runtime/control_heuristics.py`
- Modify: `backend/app/services/goal_runtime/planner.py`
- Modify: `tests/test_goal_runtime_planner.py`
- Modify: `tests/test_goal_runtime_cluster_capabilities.py`

- [ ] **Step 1: Register new capabilities**

```python
"allocation.release"
"node.drain"
"node.undrain"
```

- [ ] **Step 2: Add minimal heuristic extraction**

```python
"释放 allocation alloc-1" -> allocation.release
"排空节点 node-a" -> node.drain
"恢复节点 node-a" -> node.undrain
```

- [ ] **Step 3: Map actions in planner**

```python
"release_allocation": "allocation.release"
"drain_node": "node.drain"
"undrain_node": "node.undrain"
```

- [ ] **Step 4: Run runtime tests**

Run:

```bash
E:\Code\AI-DataCenter\.venv\Scripts\python.exe -m pytest tests/test_goal_runtime_cluster_capabilities.py tests/test_goal_runtime_planner.py -q
```

Expected: PASS.

### Task 4: Surface The New Controls In Cluster Console And Capability Forms

**Files:**
- Modify: `frontend/src/lib/controlCapabilityForms.js`
- Modify: `frontend/src/lib/controlCapabilityModels.js`
- Modify: `frontend/src/lib/clusterConsoleModels.js`
- Modify: `frontend/src/components/cluster/ClusterAllocationPanel.vue`
- Modify: `frontend/src/views/ClusterJobs.vue`
- Modify: `frontend/src/services/api.js`
- Modify: `tests/test_frontend_ui_structure.py`
- Create or Modify: `frontend/src/lib/clusterConsoleModels.test.js`

- [ ] **Step 1: Add typed forms for new capabilities**

```javascript
buildCapabilityFormDraft('node.drain')
buildCapabilityFormDraft('allocation.release')
```

- [ ] **Step 2: Enrich cluster console model**

```javascript
normalizeAllocation({ releaseable: allocation.status === 'active' })
normalizeNode(...)
```

- [ ] **Step 3: Add release action to allocation chips and refresh flow**

```vue
<button @click="$emit('release', item.id)">释放</button>
```

- [ ] **Step 4: Run frontend tests**

Run:

```bash
cd E:\Code\AI-DataCenter\frontend && npm test -- src/lib/controlCapabilityModels.test.js src/lib/clusterConsoleModels.test.js
```

Expected: PASS.

### Task 5: Full Verification

**Files:**
- Verify only

- [ ] **Step 1: Run repository-targeted regression**

Run:

```bash
E:\Code\AI-DataCenter\.venv\Scripts\python.exe -m pytest tests/test_cluster_scheduler_core.py tests/test_cluster_job_api.py tests/test_goal_runtime_cluster_capabilities.py tests/test_goal_runtime_planner.py tests/test_control_api.py tests/test_goal_runtime_capabilities.py tests/test_frontend_ui_structure.py -q
```

- [ ] **Step 2: Run frontend regression**

Run:

```bash
cd E:\Code\AI-DataCenter\frontend && npm test -- src/lib/controlCapabilityModels.test.js src/lib/clusterConsoleModels.test.js src/lib/governancePageModels.test.js
```

- [ ] **Step 3: Run production build**

Run:

```bash
cd E:\Code\AI-DataCenter\frontend && npm run build
```

- [ ] **Step 4: Confirm no unrelated files were modified**

Run:

```bash
git status --short
```
