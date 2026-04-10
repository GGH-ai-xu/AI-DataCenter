# Manual Capability Control Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working manual capability control plane: persist command records, expose a unified control API over the capability registry, add a governance capability drawer, and route first-batch human actions through the same command path used by the agent runtime.

**Architecture:** Add a new `control_plane` backend package that owns immutable command models, SQLite persistence, catalog/policy/service logic, and a unified `/api/control/*` router. Keep existing task/scheduler/cluster APIs during the transition, but introduce a governance-side command drawer and command ledger so high-frequency manual actions and agent-triggered actions converge on the same capability-backed command model.

**Tech Stack:** FastAPI, Python dataclasses, `aiosqlite`, existing goal-runtime capability registry, Vue 3, Axios, Python `unittest`, Node `node:test`.

---

## File Structure

### New files

- `backend/app/services/control_plane/__init__.py`
  - Export control-plane models and service entrypoints.
- `backend/app/services/control_plane/models.py`
  - Immutable dataclasses for command records and catalog items.
- `backend/app/services/control_plane/sqlite_support.py`
  - SQLite schema and CRUD helpers for command persistence.
- `backend/app/services/control_plane/catalog.py`
  - Convert registry entries into human-facing catalog payloads.
- `backend/app/services/control_plane/policy.py`
  - Role/risk/scope/approval checks for manual commands.
- `backend/app/services/control_plane/service.py`
  - Command creation, execution, approval, and listing orchestration.
- `backend/app/api/control.py`
  - `/api/control/*` REST routes.
- `tests/test_control_plane_models.py`
  - Persistence and model normalization tests.
- `tests/test_control_api.py`
  - Control API and service behavior tests.
- `frontend/src/lib/controlCapabilityModels.js`
  - Drawer/catalog/ledger view-model helpers.
- `frontend/src/lib/controlCapabilityModels.test.js`
  - Node tests for control capability mappers.
- `frontend/src/composables/useGovernanceControlPlane.js`
  - Shared governance control-plane state and command actions.
- `frontend/src/components/governance/CapabilityCommandDrawer.vue`
  - Capability picker, argument form, risk prompt, and result panel.
- `frontend/src/components/governance/ControlCommandLedger.vue`
  - Governance review ledger for command records.

### Modified files

- `backend/app/models/schemas.py`
  - Add request/response schemas for control commands and approvals.
- `backend/app/services/data_store.py`
  - Initialize the new control-plane tables and expose command CRUD helpers.
- `backend/app/services/goal_runtime/capability.py`
  - Add manual-control metadata to capability definitions.
- `backend/app/services/goal_runtime/capability_registry.py`
  - Add iteration helpers for catalog building.
- `backend/app/services/goal_runtime/platform_capabilities.py`
  - Mark first-batch manual capabilities with labels, descriptions, risk, role, and approval policy.
- `backend/app/main.py`
  - Instantiate the control-plane service and register the control router.
- `frontend/src/services/api.js`
  - Add `/api/control/*` helpers.
- `frontend/src/lib/governanceLoaders.js`
  - Load command records for the review section.
- `frontend/src/composables/useGovernanceData.js`
  - Surface review command records alongside evaluation data.
- `frontend/src/views/GovernanceLayout.vue`
  - Mount shared governance control-plane state and the global drawer.
- `frontend/src/views/GovernanceActionsView.vue`
  - Add trigger for advanced runtime actions and route high-frequency actions through control commands.
- `frontend/src/views/GovernancePoliciesView.vue`
  - Add trigger for strategy capabilities and route direct controls through control commands.
- `frontend/src/views/ClusterJobs.vue`
  - Route job submission through `job.submit` and expose advanced cluster actions.
- `frontend/src/views/GovernanceReviewView.vue`
  - Replace legacy action timeline with the unified command ledger.
- `frontend/src/lib/governanceReviewModel.js`
  - Map control command records into review summaries.
- `tests/test_frontend_ui_structure.py`
  - Assert the new drawer, composable, command ledger, and governance integrations.

---

### Task 1: Add Control Command Models and Persistence

**Files:**
- Create: `backend/app/services/control_plane/__init__.py`
- Create: `backend/app/services/control_plane/models.py`
- Create: `backend/app/services/control_plane/sqlite_support.py`
- Modify: `backend/app/services/data_store.py`
- Modify: `backend/app/models/schemas.py`
- Test: `tests/test_control_plane_models.py`

- [ ] **Step 1: Write the failing persistence and schema tests**

```python
# tests/test_control_plane_models.py
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.data_store import DataStore
from app.services.control_plane.models import ControlCommandRecord


class ControlPlaneModelTests(unittest.IsolatedAsyncioTestCase):
    async def test_store_round_trips_command_record_and_sorts_newest_first(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = DataStore(os.path.join(tmpdir, "control.db"))
            await store.init()
            try:
                await store.create_control_command(
                    ControlCommandRecord(
                        command_id="cmd-1",
                        capability_name="tasks.pause",
                        domain="tasks",
                        operator_id="alice",
                        operator_type="manual",
                        workspace_key="user:2",
                        source_page="governance-actions",
                        arguments={"pid": 42},
                        risk_level="control",
                        permission_mode="confirm_required",
                        approval_state="approved",
                        execution_state="succeeded",
                        result_summary="paused",
                        error_message="",
                        related_session_id="",
                    )
                )
                rows = await store.list_control_commands(limit=10)
                row = await store.get_control_command("cmd-1")
            finally:
                await store.close()

        self.assertEqual(rows[0]["command_id"], "cmd-1")
        self.assertEqual(row["arguments"]["pid"], 42)
        self.assertEqual(row["execution_state"], "succeeded")

    def test_command_record_normalizes_json_like_fields(self):
        record = ControlCommandRecord(
            command_id="cmd-2",
            capability_name="scheduler.run_once",
            domain="scheduler",
            operator_id="alice",
            operator_type="manual",
            workspace_key="user:2",
            source_page="governance-policies",
            arguments=[("acknowledge_risk", True)],
            risk_level="control",
            permission_mode="confirm_required",
            approval_state="not_required",
            execution_state="queued",
            result_summary=None,
            error_message=None,
            related_session_id=None,
        )

        self.assertEqual(record.arguments["acknowledge_risk"], True)
        self.assertEqual(record.result_summary, "")
        self.assertEqual(record.related_session_id, "")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_control_plane_models -q
```

Expected: FAIL with `ModuleNotFoundError` for `app.services.control_plane` and missing `DataStore.create_control_command`.

- [ ] **Step 3: Add the immutable command model, SQLite schema, and store helpers**

```python
# backend/app/services/control_plane/models.py
from dataclasses import dataclass


@dataclass(frozen=True)
class ControlCommandRecord:
    command_id: str
    capability_name: str
    domain: str
    operator_id: str
    operator_type: str
    workspace_key: str
    source_page: str
    arguments: dict
    risk_level: str
    permission_mode: str
    approval_state: str
    execution_state: str
    result_summary: str
    error_message: str
    related_session_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", dict(self.arguments or {}))
        object.__setattr__(self, "result_summary", self.result_summary or "")
        object.__setattr__(self, "error_message", self.error_message or "")
        object.__setattr__(self, "related_session_id", self.related_session_id or "")
```

```python
# backend/app/services/control_plane/sqlite_support.py
CONTROL_PLANE_INIT_SQL = """
CREATE TABLE IF NOT EXISTS control_commands (
    command_id TEXT PRIMARY KEY,
    capability_name TEXT NOT NULL,
    domain TEXT NOT NULL,
    operator_id TEXT NOT NULL,
    operator_type TEXT NOT NULL,
    workspace_key TEXT NOT NULL,
    source_page TEXT NOT NULL,
    arguments_json TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    permission_mode TEXT NOT NULL,
    approval_state TEXT NOT NULL,
    execution_state TEXT NOT NULL,
    result_summary TEXT NOT NULL DEFAULT '',
    error_message TEXT NOT NULL DEFAULT '',
    related_session_id TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_control_commands_created_at ON control_commands(created_at DESC);
"""
```

```python
# backend/app/services/data_store.py
from app.services.control_plane.sqlite_support import (
    CONTROL_PLANE_INIT_SQL,
    create_command as create_control_command_record,
    get_command as load_control_command,
    list_commands as load_control_commands,
    update_command as update_control_command_record,
)
...
await self._db.executescript(_INIT_SQL + GOAL_RUNTIME_INIT_SQL + CLUSTER_CONTROL_INIT_SQL + CONTROL_PLANE_INIT_SQL)
...
async def create_control_command(self, record):
    db = require_control_plane_db(self._db)
    await create_control_command_record(db, record)
    await db.commit()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_control_plane_models -q
```

Expected: PASS with `OK`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/control_plane/__init__.py \
        backend/app/services/control_plane/models.py \
        backend/app/services/control_plane/sqlite_support.py \
        backend/app/services/data_store.py \
        backend/app/models/schemas.py \
        tests/test_control_plane_models.py
git commit -m "feat: add control command persistence"
```

### Task 2: Add Control Catalog, Policy, Service, and API

**Files:**
- Create: `backend/app/services/control_plane/catalog.py`
- Create: `backend/app/services/control_plane/policy.py`
- Create: `backend/app/services/control_plane/service.py`
- Create: `backend/app/api/control.py`
- Modify: `backend/app/services/goal_runtime/capability.py`
- Modify: `backend/app/services/goal_runtime/capability_registry.py`
- Modify: `backend/app/services/goal_runtime/platform_capabilities.py`
- Modify: `backend/app/main.py`
- Test: `tests/test_control_api.py`

- [ ] **Step 1: Write the failing API and service tests**

```python
# tests/test_control_api.py
import os
import sys
import types
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.api.control import create_control_command, list_control_capabilities, approve_control_command
from app.models.schemas import ControlCommandCreateRequest, ControlCommandApprovalRequest


class ControlApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_capability_catalog_hides_non_manual_capabilities(self):
        app_state = types.SimpleNamespace(control_plane=mock.AsyncMock())
        app_state.control_plane.list_capabilities.return_value = [{"name": "tasks.pause"}]
        fake_main = types.SimpleNamespace(app_state=app_state)
        request = types.SimpleNamespace(state=types.SimpleNamespace(user={"id": 2, "role": "member"}))

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            payload = await list_control_capabilities(request)

        self.assertEqual(payload["capabilities"][0]["name"], "tasks.pause")

    async def test_member_must_acknowledge_confirm_required_capability(self):
        app_state = types.SimpleNamespace(control_plane=mock.AsyncMock())
        app_state.control_plane.create_command.side_effect = ValueError("真实执行前请先确认风险")
        fake_main = types.SimpleNamespace(app_state=app_state)
        request = types.SimpleNamespace(state=types.SimpleNamespace(user={"id": 2, "role": "member"}))

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            with self.assertRaises(Exception):
                await create_control_command(
                    request,
                    ControlCommandCreateRequest(capability_name="tasks.pause", arguments={"pid": 42}),
                )

    async def test_approve_command_returns_updated_record(self):
        app_state = types.SimpleNamespace(control_plane=mock.AsyncMock())
        app_state.control_plane.approve_command.return_value = {"command_id": "cmd-1", "execution_state": "succeeded"}
        fake_main = types.SimpleNamespace(app_state=app_state)
        request = types.SimpleNamespace(state=types.SimpleNamespace(user={"id": 1, "role": "admin"}))

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            payload = await approve_control_command(
                "cmd-1",
                request,
                ControlCommandApprovalRequest(approved=True),
            )

        self.assertEqual(payload["execution_state"], "succeeded")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_control_api -q
```

Expected: FAIL with missing `app.api.control`, missing `ControlCommandCreateRequest`, and missing control-plane service wiring.

- [ ] **Step 3: Add manual-control metadata, the control service, and the router**

```python
# backend/app/services/goal_runtime/capability.py
@dataclass(frozen=True)
class CapabilityDefinition:
    name: str
    domain: str
    side_effect_level: str
    requires_scope: bool
    supported_providers: tuple[str, ...]
    manual_enabled: bool = False
    label: str = ""
    description: str = ""
    required_role: str = "member"
    approval_policy: str = "direct"
```

```python
# backend/app/services/control_plane/service.py
class ControlPlaneService:
    def __init__(self, store, registry):
        self.store = store
        self.registry = registry

    async def list_capabilities(self, user, workspace_key):
        return build_control_catalog(self.registry, user=user, workspace_key=workspace_key)

    async def create_command(self, request, user, workspace_key):
        policy = resolve_control_policy(self.registry.get(request.capability_name).definition, user, request)
        record = build_command_record(request, user, workspace_key, policy)
        await self.store.create_control_command(record)
        if policy.approval_state == "pending":
            return serialize_command_record(record)
        return await self._execute(record)
```

```python
# backend/app/api/control.py
router = APIRouter(prefix="/api/control", tags=["Control"])

@router.get("/capabilities")
async def list_control_capabilities(request: Request):
    user = require_authenticated_user(request)
    from app.main import app_state
    return {"capabilities": await app_state.control_plane.list_capabilities(user, request.state.workspace_key)}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_control_api -q
timeout 60s ./.venv/Scripts/python.exe -m compileall backend/app/services/control_plane backend/app/api/control.py backend/app/main.py -q
```

Expected: PASS with `OK`; compile step prints no errors.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/control_plane/catalog.py \
        backend/app/services/control_plane/policy.py \
        backend/app/services/control_plane/service.py \
        backend/app/api/control.py \
        backend/app/services/goal_runtime/capability.py \
        backend/app/services/goal_runtime/capability_registry.py \
        backend/app/services/goal_runtime/platform_capabilities.py \
        backend/app/main.py \
        tests/test_control_api.py
git commit -m "feat: add manual capability control api"
```

### Task 3: Add Frontend Control API Helpers and View-Model Layer

**Files:**
- Create: `frontend/src/lib/controlCapabilityModels.js`
- Create: `frontend/src/lib/controlCapabilityModels.test.js`
- Create: `frontend/src/composables/useGovernanceControlPlane.js`
- Modify: `frontend/src/services/api.js`
- Modify: `frontend/src/lib/governanceLoaders.js`
- Modify: `frontend/src/composables/useGovernanceData.js`

- [ ] **Step 1: Write the failing frontend model tests**

```javascript
// frontend/src/lib/controlCapabilityModels.test.js
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildCapabilityDrawerModel,
  buildControlCommandTimeline,
} from './controlCapabilityModels.js'

test('buildCapabilityDrawerModel filters capabilities by governance section', () => {
  const model = buildCapabilityDrawerModel([
    { name: 'tasks.pause', domain: 'tasks', label: '暂停任务' },
    { name: 'scheduler.run_once', domain: 'scheduler', label: '执行一次调度' },
    { name: 'job.submit', domain: 'jobs', label: '提交作业' },
  ], 'actions')

  assert.deepEqual(model.items.map((item) => item.name), ['tasks.pause', 'scheduler.run_once'])
})

test('buildControlCommandTimeline sorts newest commands first', () => {
  const items = buildControlCommandTimeline([
    { command_id: 'cmd-1', created_at: 10, execution_state: 'queued' },
    { command_id: 'cmd-2', created_at: 20, execution_state: 'succeeded' },
  ])

  assert.equal(items[0].id, 'cmd-2')
  assert.equal(items[0].stateLabel, '已完成')
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
node --test frontend/src/lib/controlCapabilityModels.test.js
```

Expected: FAIL with `Cannot find module './controlCapabilityModels.js'`.

- [ ] **Step 3: Add API helpers, catalog mappers, and the governance control composable**

```javascript
// frontend/src/services/api.js
export const getControlCapabilities = () => api.get('/control/capabilities')
export const getControlCatalog = () => api.get('/control/catalog')
export const createControlCommand = (payload) => api.post('/control/commands', payload)
export const listControlCommands = (limit = 50) => api.get('/control/commands', { params: { limit } })
export const getControlCommand = (commandId) => api.get(`/control/commands/${commandId}`)
export const approveControlCommand = (commandId, approved) =>
  api.post(`/control/commands/${commandId}/approve`, { approved })
```

```javascript
// frontend/src/composables/useGovernanceControlPlane.js
export function useGovernanceControlPlane() {
  const drawer = reactive({ open: false, section: 'actions', capabilities: [], selected: null })
  async function loadCatalog() {
    const { data } = await getControlCapabilities()
    drawer.capabilities = data?.capabilities || []
  }
  return { drawer, loadCatalog, openDrawer, closeDrawer, submitCommand, approveCommand }
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
node --test frontend/src/lib/controlCapabilityModels.test.js
```

Expected: PASS with `ok`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/controlCapabilityModels.js \
        frontend/src/lib/controlCapabilityModels.test.js \
        frontend/src/composables/useGovernanceControlPlane.js \
        frontend/src/services/api.js \
        frontend/src/lib/governanceLoaders.js \
        frontend/src/composables/useGovernanceData.js
git commit -m "feat: add governance control plane frontend state"
```

### Task 4: Mount the Shared Capability Drawer in Governance Pages

**Files:**
- Create: `frontend/src/components/governance/CapabilityCommandDrawer.vue`
- Modify: `frontend/src/views/GovernanceLayout.vue`
- Modify: `frontend/src/views/GovernanceActionsView.vue`
- Modify: `frontend/src/views/GovernancePoliciesView.vue`
- Modify: `frontend/src/views/ClusterJobs.vue`
- Test: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Write the failing structure tests**

```python
# tests/test_frontend_ui_structure.py
def test_governance_pages_mount_shared_capability_drawer(self):
    layout_text = (ROOT / "frontend/src/views/GovernanceLayout.vue").read_text(encoding="utf-8")
    actions_text = (ROOT / "frontend/src/views/GovernanceActionsView.vue").read_text(encoding="utf-8")
    policies_text = (ROOT / "frontend/src/views/GovernancePoliciesView.vue").read_text(encoding="utf-8")
    cluster_text = (ROOT / "frontend/src/views/ClusterJobs.vue").read_text(encoding="utf-8")

    self.assertIn("CapabilityCommandDrawer", layout_text)
    self.assertIn("useGovernanceControlPlane", layout_text)
    self.assertIn("高级操作", actions_text)
    self.assertIn("高级能力", policies_text)
    self.assertIn("高级集群操作", cluster_text)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure -q
```

Expected: FAIL because `CapabilityCommandDrawer` and the new trigger labels do not exist yet.

- [ ] **Step 3: Add the shared drawer and governance triggers**

```vue
<!-- frontend/src/views/GovernanceLayout.vue -->
<script setup>
import CapabilityCommandDrawer from '../components/governance/CapabilityCommandDrawer.vue'
import { useGovernanceControlPlane } from '../composables/useGovernanceControlPlane.js'
...
const control = proxyRefs(useGovernanceControlPlane({ activeSection }))
</script>

<template>
  ...
  <router-view v-slot="{ Component }">
    <component :is="Component" :control="control" ... />
  </router-view>
  <CapabilityCommandDrawer :state="control.drawer" @close="control.closeDrawer" @submit="control.submitCommand" />
</template>
```

```vue
<!-- frontend/src/views/ClusterJobs.vue -->
<button type="button" class="btn-tech" @click="control.openDrawer('cluster')">
  高级集群操作
</button>
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure -q
```

Expected: PASS with `OK`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/governance/CapabilityCommandDrawer.vue \
        frontend/src/views/GovernanceLayout.vue \
        frontend/src/views/GovernanceActionsView.vue \
        frontend/src/views/GovernancePoliciesView.vue \
        frontend/src/views/ClusterJobs.vue \
        tests/test_frontend_ui_structure.py
git commit -m "feat: add governance capability drawer"
```

### Task 5: Route First-Batch Manual Actions and Review Ledger Through Control Commands

**Files:**
- Create: `frontend/src/components/governance/ControlCommandLedger.vue`
- Modify: `frontend/src/views/GovernanceActionsView.vue`
- Modify: `frontend/src/views/GovernancePoliciesView.vue`
- Modify: `frontend/src/views/ClusterJobs.vue`
- Modify: `frontend/src/views/GovernanceReviewView.vue`
- Modify: `frontend/src/lib/governanceReviewModel.js`
- Modify: `frontend/src/lib/governanceLoaders.js`
- Test: `frontend/src/lib/controlCapabilityModels.test.js`
- Test: `tests/test_frontend_ui_structure.py`
- Test: `tests/test_control_api.py`

- [ ] **Step 1: Write the failing integration and review tests**

```python
# tests/test_frontend_ui_structure.py
def test_governance_review_uses_control_command_ledger(self):
    review_text = (ROOT / "frontend/src/views/GovernanceReviewView.vue").read_text(encoding="utf-8")
    model_text = (ROOT / "frontend/src/lib/governanceReviewModel.js").read_text(encoding="utf-8")
    self.assertIn("ControlCommandLedger", review_text)
    self.assertIn("commandRecords", model_text)
    self.assertNotIn("buildGovernanceReviewTimeline(props.governance.reviewState?.auditLogs", review_text)
```

```javascript
// frontend/src/lib/controlCapabilityModels.test.js
test('buildControlCommandTimeline keeps approval-pending rows visible', () => {
  const items = buildControlCommandTimeline([
    { command_id: 'cmd-3', created_at: 30, execution_state: 'queued', approval_state: 'pending' },
  ])

  assert.equal(items[0].approvalLabel, '待审批')
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
node --test frontend/src/lib/controlCapabilityModels.test.js
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure tests.test_control_api -q
```

Expected: FAIL because governance pages still call legacy APIs directly and review still reads legacy audit logs.

- [ ] **Step 3: Rewire first-batch governance actions and the review page to control commands**

```vue
<!-- frontend/src/views/GovernanceActionsView.vue -->
async function doAction(proc, action) {
  await props.control.submitBuiltinCommand('tasks.pause', {
    pid: proc.pid,
    source_page: 'governance-actions',
    acknowledge_risk: true,
  })
  await refreshActions(true)
}
```

```javascript
// frontend/src/lib/governanceLoaders.js
async loadReviewBundle() {
  const [{ data: commandData }, { data: evaluationData }] = await Promise.all([
    api.listControlCommands(100),
    api.getScheduleEvaluation(),
  ])
  return {
    commandRecords: commandData?.commands || [],
    evaluation: evaluationData || null,
  }
}
```

```vue
<!-- frontend/src/views/GovernanceReviewView.vue -->
<ControlCommandLedger :items="commandLedger" @approve="props.control.approveCommand" />
```

- [ ] **Step 4: Run the full verification set**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_control_plane_models tests.test_control_api tests.test_frontend_ui_structure -q
node --test frontend/src/lib/controlCapabilityModels.test.js
timeout 60s ./.venv/Scripts/python.exe -m compileall backend/app/services/control_plane backend/app/api/control.py backend/app/main.py -q
```

Expected: All commands PASS; compile step prints no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/governance/ControlCommandLedger.vue \
        frontend/src/views/GovernanceActionsView.vue \
        frontend/src/views/GovernancePoliciesView.vue \
        frontend/src/views/ClusterJobs.vue \
        frontend/src/views/GovernanceReviewView.vue \
        frontend/src/lib/governanceReviewModel.js \
        frontend/src/lib/governanceLoaders.js \
        frontend/src/lib/controlCapabilityModels.test.js \
        tests/test_frontend_ui_structure.py
git commit -m "feat: route governance actions through control commands"
```

