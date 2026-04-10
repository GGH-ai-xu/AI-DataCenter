# Platform Goal Runtime Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a platform-internal goal-driven Agent runtime that turns natural-language operator goals into structured sessions with planning, approval-aware execution, strong ReAct replanning, and replayable event trails.

**Architecture:** Add a focused backend runtime package that defines immutable goal/plan/capability/session-event models, a capability registry over existing platform services, a session-aware execution supervisor, and SQLite-backed event persistence. Expose the runtime through dedicated API routes and switch the AI Assistant control tab to a session workflow so the UI reflects approval blocking, autonomous replanning, and replay instead of the current plan/execute split.

**Tech Stack:** FastAPI, Pydantic, Python dataclasses, SQLite via `aiosqlite`, existing runtime providers, Vue 3, Axios, Python `pytest`, Python `unittest`.

---

## File Structure

### New files

- `backend/app/services/goal_runtime/__init__.py`
  - Package exports for runtime service components.
- `backend/app/services/goal_runtime/goal_spec.py`
  - Immutable `GoalSpec` model and normalization helpers.
- `backend/app/services/goal_runtime/execution_plan.py`
  - `PlanStep`, `ExecutionPlan`, `StepResult`, and replan-budget structures.
- `backend/app/services/goal_runtime/capability.py`
  - `CapabilityDefinition`, side-effect level constants, and handler signatures.
- `backend/app/services/goal_runtime/session_events.py`
  - Event names, immutable session event payload helpers, and summary builders.
- `backend/app/services/goal_runtime/permission_policy.py`
  - High/low permission decisions for capability layers and approval checks.
- `backend/app/services/goal_runtime/capability_registry.py`
  - Registry object plus lookup/select APIs.
- `backend/app/services/goal_runtime/platform_capabilities.py`
  - Registry builders that wrap existing scheduler/task/energy/governance/runtime behaviors as capabilities.
- `backend/app/services/goal_runtime/goal_parser.py`
  - Natural-language goal parsing into `GoalSpec`.
- `backend/app/services/goal_runtime/planner.py`
  - Initial plan generation from `GoalSpec` plus registry/state.
- `backend/app/services/goal_runtime/executor.py`
  - Step execution against capability handlers.
- `backend/app/services/goal_runtime/supervisor.py`
  - ReAct loop, failure classification, approval blocking, and replanning.
- `backend/app/services/goal_runtime/service.py`
  - Session orchestration, persistence wiring, and API-facing methods.
- `backend/app/api/agent_runtime.py`
  - Runtime session start, approval, detail, and event replay routes.
- `tests/test_goal_runtime_models.py`
  - Unit tests for `GoalSpec`, `ExecutionPlan`, capability metadata, and session events.
- `tests/test_goal_runtime_data_store.py`
  - SQLite persistence tests for runtime sessions and events.
- `tests/test_goal_runtime_capabilities.py`
  - Capability registry and permission-policy tests.
- `tests/test_goal_runtime_planner.py`
  - Goal parsing and initial planning tests.
- `tests/test_goal_runtime_supervisor.py`
  - ReAct loop tests for high-permission reroute and low-permission approval blocking.
- `tests/test_goal_runtime_api.py`
  - FastAPI-level tests for runtime session endpoints.
- `frontend/src/components/agent/AgentSessionTimeline.vue`
  - Compact event-trail / approval / completion summary component for the assistant page.

### Modified files

- `backend/app/models/schemas.py`
  - Adds runtime session request/response schemas and approval payloads.
- `backend/app/services/data_store.py`
  - Adds agent session and agent event tables plus CRUD methods.
- `backend/app/main.py`
  - Adds `goal_runtime` to `AppState`, instantiates the runtime service, and registers the router.
- `backend/app/api/ai.py`
  - Routes legacy AI control actions through the runtime-compatible path or compatibility helpers.
- `backend/app/services/ai_control.py`
  - Shrinks into reusable heuristic parsing helpers and compatibility adapters instead of owning execution.
- `frontend/src/services/api.js`
  - Adds goal-runtime session API helpers.
- `frontend/src/views/AIAssistant.vue`
  - Replaces plan/execute-only control flow with runtime session creation, approval, and timeline display.
- `tests/test_frontend_ui_structure.py`
  - Structural checks for runtime session UI wiring and removed direct control-only calls.
- `backend/tests/test_ai_control.py`
  - Keeps compatibility coverage for legacy helper behavior.

---

### Task 1: Build Runtime Domain Models

**Files:**
- Create: `backend/app/services/goal_runtime/__init__.py`
- Create: `backend/app/services/goal_runtime/goal_spec.py`
- Create: `backend/app/services/goal_runtime/execution_plan.py`
- Create: `backend/app/services/goal_runtime/capability.py`
- Create: `backend/app/services/goal_runtime/session_events.py`
- Modify: `backend/app/models/schemas.py`
- Test: `tests/test_goal_runtime_models.py`

- [ ] **Step 1: Write the failing model tests**

```python
from app.services.goal_runtime.goal_spec import GoalSpec, normalize_permission_mode
from app.services.goal_runtime.execution_plan import PlanStep, ExecutionPlan
from app.services.goal_runtime.capability import CapabilityDefinition
from app.services.goal_runtime.session_events import build_goal_parsed_event


def test_goal_spec_normalizes_permission_mode_and_scope():
    spec = GoalSpec(
        session_id="sess-1",
        raw_message="把总功率压到 1200W 以下",
        goal_type="runtime_control",
        permission_mode="HIGH",
        scope_gpu_indexes=(3, 1, 3),
        constraints=("不影响 urgent 任务",),
        done_when="current_total_power <= 1200",
        abort_when=("no_capability_path",),
    )

    assert normalize_permission_mode("HIGH") == "high"
    assert spec.permission_mode == "high"
    assert spec.scope_gpu_indexes == (1, 3)


def test_execution_plan_tracks_steps_and_replan_budget():
    step = PlanStep(
        step_id="step-read",
        capability_name="runtime.snapshot.read",
        arguments={},
        approval_required=False,
    )
    plan = ExecutionPlan(plan_id="plan-1", steps=(step,), replan_budget=3)

    assert plan.remaining_step_ids() == ("step-read",)
    assert plan.can_replan() is True


def test_capability_definition_exposes_side_effect_layer():
    definition = CapabilityDefinition(
        name="tasks.pause",
        domain="tasks",
        side_effect_level="runtime_action",
        requires_scope=True,
        supported_providers=("http_local", "ssh_linux"),
    )

    assert definition.side_effect_level == "runtime_action"
    assert definition.requires_scope is True


def test_goal_parsed_event_payload_contains_summary_fields():
    event = build_goal_parsed_event(
        session_id="sess-1",
        goal_type="runtime_control",
        permission_mode="low",
        summary="降低总功率且不影响 urgent 任务",
    )

    assert event.event_type == "GoalParsed"
    assert event.payload["permission_mode"] == "low"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
timeout 60s python -m pytest tests/test_goal_runtime_models.py -q
```

Expected: FAIL because the `goal_runtime` package and runtime models do not exist yet.

- [ ] **Step 3: Write immutable runtime models**

```python
# backend/app/services/goal_runtime/goal_spec.py
from dataclasses import dataclass


def normalize_permission_mode(value: str | None) -> str:
    return "high" if str(value or "").lower() == "high" else "low"


@dataclass(frozen=True)
class GoalSpec:
    session_id: str
    raw_message: str
    goal_type: str
    permission_mode: str
    scope_gpu_indexes: tuple[int, ...]
    constraints: tuple[str, ...]
    done_when: str
    abort_when: tuple[str, ...]

    def __post_init__(self):
        object.__setattr__(self, "permission_mode", normalize_permission_mode(self.permission_mode))
        object.__setattr__(self, "scope_gpu_indexes", tuple(sorted(set(self.scope_gpu_indexes))))
```

```python
# backend/app/services/goal_runtime/execution_plan.py
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    capability_name: str
    arguments: dict
    approval_required: bool = False
    fallback_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExecutionPlan:
    plan_id: str
    steps: tuple[PlanStep, ...]
    replan_budget: int = 0

    def remaining_step_ids(self) -> tuple[str, ...]:
        return tuple(step.step_id for step in self.steps)

    def can_replan(self) -> bool:
        return self.replan_budget > 0
```

```python
# backend/app/services/goal_runtime/capability.py
from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilityDefinition:
    name: str
    domain: str
    side_effect_level: str
    requires_scope: bool
    supported_providers: tuple[str, ...]
```

- [ ] **Step 4: Add event helpers and request schemas**

```python
# backend/app/services/goal_runtime/session_events.py
from dataclasses import dataclass
import time


@dataclass(frozen=True)
class SessionEvent:
    session_id: str
    event_type: str
    payload: dict
    timestamp: float


def build_goal_parsed_event(session_id: str, goal_type: str, permission_mode: str, summary: str) -> SessionEvent:
    return SessionEvent(
        session_id=session_id,
        event_type="GoalParsed",
        payload={
            "goal_type": goal_type,
            "permission_mode": permission_mode,
            "summary": summary,
        },
        timestamp=time.time(),
    )
```

```python
# backend/app/models/schemas.py
class AgentRuntimeStartRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    permission_mode: str = Field(default="low", pattern=r"^(high|low)$")


class AgentRuntimeApprovalRequest(BaseModel):
    approved: bool


class AgentRuntimeSessionResponse(BaseModel):
    session_id: str
    status: str
    permission_mode: str
    summary: str = ""
    requires_approval: bool = False
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
timeout 60s python -m pytest tests/test_goal_runtime_models.py -q
```

Expected: PASS with runtime model tests green.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/goal_runtime/__init__.py \
  backend/app/services/goal_runtime/goal_spec.py \
  backend/app/services/goal_runtime/execution_plan.py \
  backend/app/services/goal_runtime/capability.py \
  backend/app/services/goal_runtime/session_events.py \
  backend/app/models/schemas.py \
  tests/test_goal_runtime_models.py
git commit -m "feat: add goal runtime domain models"
```

### Task 2: Persist Runtime Sessions And Event Trails

**Files:**
- Modify: `backend/app/services/data_store.py`
- Test: `tests/test_goal_runtime_data_store.py`

- [ ] **Step 1: Write the failing persistence tests**

```python
import tempfile

import pytest

from app.services.data_store import DataStore


@pytest.mark.asyncio
async def test_data_store_persists_runtime_session_and_events():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = DataStore(f"{tmpdir}/runtime.db")
        await store.init()

        await store.create_agent_session(
            session_id="sess-1",
            goal_json={"message": "分析当前集群"},
            permission_mode="low",
            status="running",
            summary="分析当前集群",
        )
        await store.append_agent_event(
            session_id="sess-1",
            event_type="GoalParsed",
            payload={"summary": "分析当前集群"},
        )

        session = await store.get_agent_session("sess-1")
        events = await store.get_agent_events("sess-1")

        assert session["status"] == "running"
        assert events[0]["event_type"] == "GoalParsed"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
timeout 60s python -m pytest tests/test_goal_runtime_data_store.py -q
```

Expected: FAIL because runtime session tables and methods do not exist yet.

- [ ] **Step 3: Add SQLite tables for runtime sessions and events**

```sql
CREATE TABLE IF NOT EXISTS agent_runtime_sessions (
    session_id TEXT PRIMARY KEY,
    goal_json TEXT NOT NULL,
    permission_mode TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_runtime_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    timestamp REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_runtime_events_session_ts
    ON agent_runtime_events(session_id, timestamp);
```

- [ ] **Step 4: Add DataStore CRUD methods**

```python
async def create_agent_session(self, session_id: str, goal_json: dict, permission_mode: str, status: str, summary: str):
    now = time.time()
    await self._db.execute(
        """INSERT INTO agent_runtime_sessions
           (session_id, goal_json, permission_mode, status, summary, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (session_id, json.dumps(goal_json, ensure_ascii=False), permission_mode, status, summary, now, now),
    )
    await self._db.commit()


async def append_agent_event(self, session_id: str, event_type: str, payload: dict):
    await self._db.execute(
        """INSERT INTO agent_runtime_events (session_id, event_type, payload_json, timestamp)
           VALUES (?, ?, ?, ?)""",
        (session_id, event_type, json.dumps(payload, ensure_ascii=False), time.time()),
    )
    await self._db.commit()
```

- [ ] **Step 5: Add update and replay helpers**

```python
async def update_agent_session_status(self, session_id: str, status: str, summary: str = ""):
    await self._db.execute(
        """UPDATE agent_runtime_sessions
           SET status = ?, summary = ?, updated_at = ?
           WHERE session_id = ?""",
        (status, summary, time.time(), session_id),
    )
    await self._db.commit()


async def get_agent_session(self, session_id: str) -> dict | None:
    cursor = await self._db.execute(
        "SELECT * FROM agent_runtime_sessions WHERE session_id = ?",
        (session_id,),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_agent_events(self, session_id: str) -> list[dict]:
    cursor = await self._db.execute(
        "SELECT * FROM agent_runtime_events WHERE session_id = ? ORDER BY id ASC",
        (session_id,),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]
```

- [ ] **Step 6: Run persistence tests**

Run:

```bash
timeout 60s python -m pytest tests/test_goal_runtime_data_store.py -q
```

Expected: PASS with runtime session persistence verified.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/data_store.py tests/test_goal_runtime_data_store.py
git commit -m "feat: persist goal runtime sessions"
```

### Task 3: Build Capability Registry And Permission Policy

**Files:**
- Create: `backend/app/services/goal_runtime/permission_policy.py`
- Create: `backend/app/services/goal_runtime/capability_registry.py`
- Create: `backend/app/services/goal_runtime/platform_capabilities.py`
- Test: `tests/test_goal_runtime_capabilities.py`

- [ ] **Step 1: Write the failing registry and permission tests**

```python
from app.services.goal_runtime.capability_registry import CapabilityRegistry
from app.services.goal_runtime.permission_policy import requires_approval
from app.services.goal_runtime.capability import CapabilityDefinition


def test_permission_policy_only_requires_approval_for_runtime_actions_in_low_mode():
    read_cap = CapabilityDefinition("runtime.snapshot.read", "runtime", "observe", False, ("http_local",))
    act_cap = CapabilityDefinition("tasks.pause", "tasks", "runtime_action", True, ("http_local",))

    assert requires_approval(read_cap, "low") is False
    assert requires_approval(act_cap, "low") is True
    assert requires_approval(act_cap, "high") is False


def test_capability_registry_returns_registered_definition():
    registry = CapabilityRegistry()
    definition = CapabilityDefinition("tasks.pause", "tasks", "runtime_action", True, ("http_local",))

    registry.register(definition, handler=lambda ctx, args: {"success": True})
    selected = registry.get("tasks.pause")

    assert selected.definition.name == "tasks.pause"
    assert callable(selected.handler)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
timeout 60s python -m pytest tests/test_goal_runtime_capabilities.py -q
```

Expected: FAIL because registry and permission-policy modules do not exist yet.

- [ ] **Step 3: Implement registry and approval policy**

```python
# backend/app/services/goal_runtime/capability_registry.py
from dataclasses import dataclass


@dataclass(frozen=True)
class RegisteredCapability:
    definition: object
    handler: object


class CapabilityRegistry:
    def __init__(self):
        self._items = {}

    def register(self, definition, handler):
        self._items[definition.name] = RegisteredCapability(definition=definition, handler=handler)

    def get(self, name: str):
        return self._items[name]
```

```python
# backend/app/services/goal_runtime/permission_policy.py
RUNTIME_ACTION_LEVEL = "runtime_action"


def requires_approval(definition, permission_mode: str) -> bool:
    return permission_mode == "low" and definition.side_effect_level == RUNTIME_ACTION_LEVEL
```

- [ ] **Step 4: Register platform capabilities over existing services**

```python
def build_platform_capability_registry(app_state) -> CapabilityRegistry:
    registry = CapabilityRegistry()

    registry.register(
        CapabilityDefinition("runtime.snapshot.read", "runtime", "observe", False, ("http_local", "http_remote", "ssh_linux")),
        handler=lambda ctx, args: ctx["snapshot"],
    )
    registry.register(
        CapabilityDefinition("tasks.pause", "tasks", "runtime_action", True, ("http_local", "http_remote", "ssh_linux")),
        handler=lambda ctx, args: app_state.agent.pause_task(args["pid"]),
    )
    registry.register(
        CapabilityDefinition("scheduler.power_limit.set", "scheduler", "runtime_action", True, ("http_local", "http_remote", "ssh_linux")),
        handler=lambda ctx, args: app_state.agent.set_power_limit(args["gpu_index"], args["power_limit"]),
    )
    return registry
```

- [ ] **Step 5: Add tests for provider compatibility and missing capability lookups**

```python
def test_runtime_action_capability_declares_scope_and_provider_support():
    registry = build_platform_capability_registry(FakeAppState())
    pause = registry.get("tasks.pause").definition

    assert pause.requires_scope is True
    assert "ssh_linux" in pause.supported_providers
```

- [ ] **Step 6: Run capability tests**

Run:

```bash
timeout 60s python -m pytest tests/test_goal_runtime_capabilities.py -q
```

Expected: PASS with registry and permission decisions verified.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/goal_runtime/permission_policy.py \
  backend/app/services/goal_runtime/capability_registry.py \
  backend/app/services/goal_runtime/platform_capabilities.py \
  tests/test_goal_runtime_capabilities.py
git commit -m "feat: add goal runtime capability registry"
```

### Task 4: Implement Goal Parsing And Initial Planning

**Files:**
- Create: `backend/app/services/goal_runtime/goal_parser.py`
- Create: `backend/app/services/goal_runtime/planner.py`
- Modify: `backend/app/services/ai_control.py`
- Test: `tests/test_goal_runtime_planner.py`

- [ ] **Step 1: Write the failing parser/planner tests**

```python
import pytest

from app.services.goal_runtime.goal_parser import parse_goal_message
from app.services.goal_runtime.planner import build_initial_plan


@pytest.mark.asyncio
async def test_parse_goal_message_extracts_runtime_control_constraints():
    spec = await parse_goal_message(
        session_id="sess-1",
        message="把当前导入机器的总功率压到 1200W 以下，但不要影响 urgent 任务",
        permission_mode="high",
        import_context=FakeImportContext([0, 1]),
        llm_service=None,
    )

    assert spec.goal_type == "runtime_control"
    assert "urgent" in " ".join(spec.constraints)
    assert spec.scope_gpu_indexes == (0, 1)


def test_build_initial_plan_prefers_read_then_scheduler_actions():
    plan = build_initial_plan(
        goal_spec=FakeRuntimeControlGoalSpec(),
        registry=FakeRegistry(["runtime.snapshot.read", "scheduler.power_limit.set", "tasks.pause"]),
    )

    assert plan.steps[0].capability_name == "runtime.snapshot.read"
    assert plan.steps[-1].capability_name in {"scheduler.power_limit.set", "tasks.pause"}
```

- [ ] **Step 2: Run parser/planner tests to verify failure**

Run:

```bash
timeout 60s python -m pytest tests/test_goal_runtime_planner.py -q
```

Expected: FAIL because parser and planner do not exist yet.

- [ ] **Step 3: Parse natural-language goals into `GoalSpec`**

```python
async def parse_goal_message(session_id, message, permission_mode, import_context, llm_service):
    normalized = message.strip()
    constraints = []
    if "urgent" in normalized.lower() or "紧急" in normalized:
        constraints.append("do_not_interrupt_urgent_tasks")
    goal_type = "runtime_control" if any(token in normalized for token in ("功率", "预算", "暂停", "恢复", "调度")) else "analysis"
    done_when = "analysis_generated" if goal_type == "analysis" else "goal_constraints_satisfied"
    return GoalSpec(
        session_id=session_id,
        raw_message=normalized,
        goal_type=goal_type,
        permission_mode=permission_mode,
        scope_gpu_indexes=tuple(import_context.selected_gpu_indexes()),
        constraints=tuple(constraints),
        done_when=done_when,
        abort_when=("no_capability_path",),
    )
```

- [ ] **Step 4: Build initial plans from capability graph**

```python
def build_initial_plan(goal_spec, registry):
    if goal_spec.goal_type == "analysis":
        return ExecutionPlan(
            plan_id=f"{goal_spec.session_id}-plan",
            steps=(
                PlanStep("step-read", "runtime.snapshot.read", {}, approval_required=False),
            ),
            replan_budget=3,
        )
    return ExecutionPlan(
        plan_id=f"{goal_spec.session_id}-plan",
        steps=(
            PlanStep("step-read", "runtime.snapshot.read", {}, approval_required=False),
            PlanStep("step-power", "scheduler.power_limit.set", {"mode": "auto"}, approval_required=True, fallback_capabilities=("tasks.pause",)),
        ),
        replan_budget=3,
    )
```

- [ ] **Step 5: Reuse existing AI control heuristics instead of duplicating parsing rules**

```python
# backend/app/services/ai_control.py
def build_control_heuristic(message: str) -> dict:
    return _build_heuristic_plan(message)
```

```python
# backend/app/services/goal_runtime/goal_parser.py
from app.services.ai_control import build_control_heuristic
```

- [ ] **Step 6: Run parser/planner tests**

Run:

```bash
timeout 60s python -m pytest tests/test_goal_runtime_planner.py -q
```

Expected: PASS with `GoalSpec` parsing and initial planning working.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/goal_runtime/goal_parser.py \
  backend/app/services/goal_runtime/planner.py \
  backend/app/services/ai_control.py \
  tests/test_goal_runtime_planner.py
git commit -m "feat: add goal runtime parsing and planning"
```

### Task 5: Implement Step Executor And ReAct Supervisor

**Files:**
- Create: `backend/app/services/goal_runtime/executor.py`
- Create: `backend/app/services/goal_runtime/supervisor.py`
- Test: `tests/test_goal_runtime_supervisor.py`

- [ ] **Step 1: Write the failing supervisor tests**

```python
import pytest

from app.services.goal_runtime.supervisor import execute_plan_session


@pytest.mark.asyncio
async def test_high_permission_reroutes_to_fallback_without_approval():
    result = await execute_plan_session(
        session_id="sess-1",
        goal_spec=FakeGoalSpec(permission_mode="high"),
        plan=FakePlan(primary="scheduler.power_limit.set", fallback="tasks.pause"),
        registry=FakeRegistry(fail_primary=True),
        persistence=FakePersistence(),
    )

    assert result["status"] == "completed"
    assert "PlanRevised" in result["event_types"]


@pytest.mark.asyncio
async def test_low_permission_blocks_when_react_introduces_runtime_action():
    result = await execute_plan_session(
        session_id="sess-2",
        goal_spec=FakeGoalSpec(permission_mode="low"),
        plan=FakePlan(primary="runtime.snapshot.read", fallback="tasks.pause"),
        registry=FakeRegistry(require_runtime_action=True),
        persistence=FakePersistence(),
    )

    assert result["status"] == "awaiting_approval"
    assert result["pending_approval"]["actions"][0]["capability_name"] == "tasks.pause"
```

- [ ] **Step 2: Run the failing supervisor tests**

Run:

```bash
timeout 60s python -m pytest tests/test_goal_runtime_supervisor.py -q
```

Expected: FAIL because executor and supervisor do not exist yet.

- [ ] **Step 3: Implement capability execution wrapper**

```python
async def execute_step(registry, step, context):
    registered = registry.get(step.capability_name)
    result = await registered.handler(context, step.arguments) if hasattr(registered.handler, "__call__") else registered.handler(context, step.arguments)
    return {
        "step_id": step.step_id,
        "capability_name": step.capability_name,
        "result": result,
    }
```

- [ ] **Step 4: Implement failure classification and replanning**

```python
def classify_step_failure(error: Exception | None, step, fallback_capability: str | None):
    if fallback_capability:
        return "recoverable"
    if step.approval_required:
        return "approval_blocked"
    return "terminal"


def revise_plan_with_fallback(plan, failed_step_id: str, fallback_capability: str):
    revised_steps = []
    for step in plan.steps:
        if step.step_id == failed_step_id:
            revised_steps.append(
                PlanStep(step.step_id, fallback_capability, step.arguments, approval_required=True)
            )
        else:
            revised_steps.append(step)
    return ExecutionPlan(plan.plan_id + "-r1", tuple(revised_steps), plan.replan_budget - 1)
```

- [ ] **Step 5: Implement the supervisor loop**

```python
async def execute_plan_session(session_id, goal_spec, plan, registry, persistence):
    event_types = []
    current_plan = plan

    for step in current_plan.steps:
        try:
            result = await execute_step(registry, step, {"session_id": session_id})
            await persistence.append_event(session_id, "StepExecuted", result)
            event_types.append("StepExecuted")
            continue
        except Exception as exc:
            fallback = step.fallback_capabilities[0] if step.fallback_capabilities else None
            classification = classify_step_failure(exc, step, fallback)
            if classification == "recoverable" and goal_spec.permission_mode == "high":
                current_plan = revise_plan_with_fallback(current_plan, step.step_id, fallback)
                await persistence.append_event(session_id, "PlanRevised", {"failed_step_id": step.step_id, "fallback": fallback})
                event_types.append("PlanRevised")
                return await execute_plan_session(session_id, goal_spec, current_plan, registry, persistence)
            if classification in {"recoverable", "approval_blocked"}:
                return {"status": "awaiting_approval", "event_types": event_types, "pending_approval": {"actions": [{"capability_name": fallback or step.capability_name}]}}
            return {"status": "failed", "event_types": event_types, "error": str(exc)}

    return {"status": "completed", "event_types": event_types}
```

- [ ] **Step 6: Run the supervisor tests**

Run:

```bash
timeout 60s python -m pytest tests/test_goal_runtime_supervisor.py -q
```

Expected: PASS with autonomous high-permission reroute and low-permission approval blocking verified.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/goal_runtime/executor.py \
  backend/app/services/goal_runtime/supervisor.py \
  tests/test_goal_runtime_supervisor.py
git commit -m "feat: add goal runtime react supervisor"
```

### Task 6: Add Runtime Service And API Routes

**Files:**
- Create: `backend/app/services/goal_runtime/service.py`
- Create: `backend/app/api/agent_runtime.py`
- Modify: `backend/app/main.py`
- Test: `tests/test_goal_runtime_api.py`

- [ ] **Step 1: Write the failing API tests**

```python
import types

import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_start_runtime_session_returns_awaiting_approval_for_low_mode(monkeypatch):
    from app.api.agent_runtime import router
    from app.main import app

    fake_runtime = FakeGoalRuntimeService(status="awaiting_approval")
    monkeypatch.setattr("app.main.app_state", types.SimpleNamespace(goal_runtime=fake_runtime))
    client = TestClient(app)

    response = client.post("/api/agent-runtime/sessions", json={"message": "暂停当前低优先级任务", "permission_mode": "low"})

    assert response.status_code == 200
    assert response.json()["status"] == "awaiting_approval"
```

- [ ] **Step 2: Run the failing API tests**

Run:

```bash
timeout 60s python -m pytest tests/test_goal_runtime_api.py -q
```

Expected: FAIL because runtime service and API routes do not exist yet.

- [ ] **Step 3: Implement `GoalRuntimeService` orchestration**

```python
class GoalRuntimeService:
    def __init__(self, store, registry, import_context, runtime_status_reader):
        self.store = store
        self.registry = registry
        self.import_context = import_context
        self.runtime_status_reader = runtime_status_reader

    async def append_event(self, session_id: str, event_type: str, payload: dict):
        await self.store.append_agent_event(session_id, event_type, payload)

    async def preview_session(self, message: str, permission_mode: str):
        session_id = uuid4().hex
        goal_spec = await parse_goal_message(session_id, message, permission_mode, self.import_context, None)
        plan = build_initial_plan(goal_spec, self.registry)
        return {
            "session_id": session_id,
            "summary": goal_spec.raw_message,
            "requires_approval": any(step.approval_required for step in plan.steps if permission_mode == "low"),
            "actions": [{"capability_name": step.capability_name, "arguments": step.arguments} for step in plan.steps],
        }

    async def start_session(self, message: str, permission_mode: str):
        session_id = uuid4().hex
        goal_spec = await parse_goal_message(session_id, message, permission_mode, self.import_context, None)
        plan = build_initial_plan(goal_spec, self.registry)
        await self.store.create_agent_session(session_id, {"message": message}, permission_mode, "running", message)
        await self.store.append_agent_event(session_id, "GoalParsed", {"goal_type": goal_spec.goal_type})
        return await execute_plan_session(session_id, goal_spec, plan, self.registry, self)

    async def resolve_approval(self, session_id: str, approved: bool):
        return {"session_id": session_id, "status": "completed" if approved else "aborted"}

    async def get_session(self, session_id: str):
        return await self.store.get_agent_session(session_id)

    async def get_events(self, session_id: str):
        return await self.store.get_agent_events(session_id)
```

- [ ] **Step 4: Add API routes for start, approve, detail, and replay**

```python
router = APIRouter(prefix="/api/agent-runtime", tags=["Agent Runtime"])


@router.post("/sessions")
async def start_agent_runtime_session(req: AgentRuntimeStartRequest):
    from app.main import app_state
    return await app_state.goal_runtime.start_session(req.message, req.permission_mode)


@router.post("/sessions/{session_id}/approve")
async def approve_agent_runtime_session(session_id: str, req: AgentRuntimeApprovalRequest):
    from app.main import app_state
    return await app_state.goal_runtime.resolve_approval(session_id, req.approved)


@router.get("/sessions/{session_id}")
async def get_agent_runtime_session(session_id: str):
    from app.main import app_state
    return await app_state.goal_runtime.get_session(session_id)


@router.get("/sessions/{session_id}/events")
async def get_agent_runtime_events(session_id: str):
    from app.main import app_state
    return {"events": await app_state.goal_runtime.get_events(session_id)}
```

- [ ] **Step 5: Wire the runtime into `AppState` and FastAPI**

```python
class AppState:
    goal_runtime: object
```

```python
app_state.goal_runtime = GoalRuntimeService(
    store=app_state.store,
    registry=build_platform_capability_registry(app_state),
    import_context=app_state.import_context,
    runtime_status_reader=runtime_status_payload,
)
```

```python
app.include_router(agent_runtime_router)
```

- [ ] **Step 6: Run API tests**

Run:

```bash
timeout 60s python -m pytest tests/test_goal_runtime_api.py -q
```

Expected: PASS with low-permission session start, approval resolution, and event replay routes working.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/goal_runtime/service.py \
  backend/app/api/agent_runtime.py \
  backend/app/main.py \
  tests/test_goal_runtime_api.py
git commit -m "feat: expose goal runtime session api"
```

### Task 7: Replace Assistant Control Tab With Session Workflow

**Files:**
- Create: `frontend/src/components/agent/AgentSessionTimeline.vue`
- Modify: `frontend/src/services/api.js`
- Modify: `frontend/src/views/AIAssistant.vue`
- Test: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Write the failing structural test**

```python
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AgentRuntimeUiStructureTest(unittest.TestCase):
    def test_ai_assistant_uses_runtime_session_api(self):
        text = (ROOT / "frontend/src/views/AIAssistant.vue").read_text(encoding="utf-8")
        api_text = (ROOT / "frontend/src/services/api.js").read_text(encoding="utf-8")

        self.assertIn("startAgentRuntimeSession", api_text)
        self.assertIn("approveAgentRuntimeSession", api_text)
        self.assertIn("AgentSessionTimeline", text)
        self.assertNotIn("aiControlPlan(", text)
```

- [ ] **Step 2: Run the failing UI structure test**

Run:

```bash
timeout 60s python -m unittest tests.test_frontend_ui_structure.AgentRuntimeUiStructureTest -q
```

Expected: FAIL because the assistant still uses the legacy control endpoints.

- [ ] **Step 3: Add runtime API helpers**

```js
export const startAgentRuntimeSession = (message, permission_mode = 'low') =>
  api.post('/agent-runtime/sessions', { message, permission_mode })

export const approveAgentRuntimeSession = (sessionId, approved) =>
  api.post(`/agent-runtime/sessions/${sessionId}/approve`, { approved })

export const getAgentRuntimeSessionEvents = (sessionId) =>
  api.get(`/agent-runtime/sessions/${sessionId}/events`)
```

- [ ] **Step 4: Add a compact session timeline component**

```vue
<script setup>
defineProps({
  session: { type: Object, default: null },
  events: { type: Array, default: () => [] },
})
</script>

<template>
  <section class="agent-session-timeline">
    <header>
      <h3>任务轨迹</h3>
      <p>{{ session?.status || '未开始' }}</p>
    </header>
    <ol>
      <li v-for="event in events" :key="`${event.id || event.timestamp}-${event.event_type}`">
        <strong>{{ event.event_type }}</strong>
        <span>{{ event.payload_json || event.summary || '' }}</span>
      </li>
    </ol>
  </section>
</template>
```

- [ ] **Step 5: Move `AIAssistant.vue` control tab to session orchestration**

```js
import {
  aiChat,
  approveAgentRuntimeSession,
  getAgentRuntimeSessionEvents,
  startAgentRuntimeSession,
  getLlmConfig,
  testLlmConfig,
  updateLlmConfig,
} from '../services/api'
import AgentSessionTimeline from '../components/agent/AgentSessionTimeline.vue'
```

```js
const runtimeSession = ref(null)
const runtimeEvents = ref([])
const controlPermissionMode = ref('low')

async function generateControlPlan() {
  const message = controlInput.value.trim()
  if (!message || controlPlanning.value) return
  controlPlanning.value = true
  try {
    const { data } = await startAgentRuntimeSession(message, controlPermissionMode.value)
    runtimeSession.value = data
    if (data?.session_id) {
      const eventsResponse = await getAgentRuntimeSessionEvents(data.session_id)
      runtimeEvents.value = eventsResponse.data.events || []
    }
  } finally {
    controlPlanning.value = false
  }
}
```

```vue
<label class="assistant-control-mode">
  <span>执行权限</span>
  <select v-model="controlPermissionMode">
    <option value="low">低权限</option>
    <option value="high">高权限</option>
  </select>
</label>
```

- [ ] **Step 6: Run the structural test**

Run:

```bash
timeout 60s python -m unittest tests.test_frontend_ui_structure.AgentRuntimeUiStructureTest -q
```

Expected: PASS with runtime session API usage and timeline rendering present.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/agent/AgentSessionTimeline.vue \
  frontend/src/services/api.js \
  frontend/src/views/AIAssistant.vue \
  tests/test_frontend_ui_structure.py
git commit -m "feat: switch assistant control tab to runtime sessions"
```

### Task 8: Collapse Legacy AI Control Into Compatibility Helpers

**Files:**
- Modify: `backend/app/api/ai.py`
- Modify: `backend/app/services/ai_control.py`
- Modify: `backend/tests/test_ai_control.py`

- [ ] **Step 1: Write the failing compatibility test**

```python
import pytest

from app.services.ai_control import build_control_heuristic


def test_build_control_heuristic_still_extracts_pause_action():
    plan = build_control_heuristic("暂停 PID 1234")
    assert plan["actions"][0]["action"] == "pause_task"
```

```python
@pytest.mark.asyncio
async def test_ai_control_plan_route_can_delegate_to_runtime_preview(monkeypatch):
    from app.api.ai import control_plan

    monkeypatch.setattr("app.main.app_state", FakeAppStateWithGoalRuntime())
    response = await control_plan(type("Req", (), {"message": "暂停 PID 1234"})())

    assert response["planner"] == "runtime"
    assert "session_id" in response
```

- [ ] **Step 2: Run compatibility tests to verify failure**

Run:

```bash
timeout 60s python -m pytest backend/tests/test_ai_control.py -q
```

Expected: FAIL because the API still owns the legacy direct plan/execute path.

- [ ] **Step 3: Preserve heuristic extraction as a compatibility helper**

```python
def build_control_heuristic(message: str) -> dict:
    return _build_heuristic_plan(message)
```

- [ ] **Step 4: Delegate the legacy control-plan route to runtime preview**

```python
@router.post("/control/plan")
async def control_plan(req: AIControlPlanRequest):
    from app.main import app_state
    preview = await app_state.goal_runtime.preview_session(req.message, permission_mode="low")
    return {
        "planner": "runtime",
        "session_id": preview["session_id"],
        "summary": preview["summary"],
        "requires_confirmation": preview["requires_approval"],
        "actions": preview.get("actions", []),
    }
```

- [ ] **Step 5: Delegate the legacy execute route to approval resolution**

```python
@router.post("/control/execute")
async def control_execute(req: AIControlExecuteRequest):
    from app.main import app_state
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="执行前请提供原始目标")
    preview = await app_state.goal_runtime.preview_session(req.message, permission_mode="low")
    return await app_state.goal_runtime.resolve_approval(preview["session_id"], req.acknowledge_risk)
```

- [ ] **Step 6: Run compatibility tests**

Run:

```bash
timeout 60s python -m pytest backend/tests/test_ai_control.py -q
```

Expected: PASS with legacy helper behavior preserved and route delegation in place.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/ai.py backend/app/services/ai_control.py backend/tests/test_ai_control.py
git commit -m "refactor: route ai control through goal runtime"
```

### Task 9: Full Regression Sweep For Runtime Introduction

**Files:**
- Test only: `tests/test_goal_runtime_models.py`
- Test only: `tests/test_goal_runtime_data_store.py`
- Test only: `tests/test_goal_runtime_capabilities.py`
- Test only: `tests/test_goal_runtime_planner.py`
- Test only: `tests/test_goal_runtime_supervisor.py`
- Test only: `tests/test_goal_runtime_api.py`
- Test only: `backend/tests/test_ai_control.py`
- Test only: `tests/test_scheduler.py`
- Test only: `tests/test_runtime_snapshot_routes.py`
- Test only: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Run the new runtime backend test set**

Run:

```bash
timeout 60s python -m pytest \
  tests/test_goal_runtime_models.py \
  tests/test_goal_runtime_data_store.py \
  tests/test_goal_runtime_capabilities.py \
  tests/test_goal_runtime_planner.py \
  tests/test_goal_runtime_supervisor.py \
  tests/test_goal_runtime_api.py \
  backend/tests/test_ai_control.py -q
```

Expected: PASS with all runtime-focused tests green.

- [ ] **Step 2: Run targeted regression tests for existing scheduling and scoped runtime behavior**

Run:

```bash
timeout 60s python -m pytest \
  tests/test_scheduler.py \
  tests/test_runtime_snapshot_routes.py -q
```

Expected: PASS with no regression in scheduler APIs or scoped snapshot routes.

- [ ] **Step 3: Run frontend structural regression**

Run:

```bash
timeout 60s python -m unittest tests.test_frontend_ui_structure -q
```

Expected: PASS with assistant runtime UI structure intact.

- [ ] **Step 4: Commit the verification-only checkpoint**

```bash
git add -A
git commit -m "test: verify goal runtime integration"
```

---

## Self-Review

### Spec coverage

- Goal runtime core chain is covered by Tasks 1, 4, 5, and 6.
- `GoalSpec / ExecutionPlan / Capability` first-class objects are covered by Tasks 1, 3, and 4.
- High/low permission model and approval gate are covered by Tasks 3, 5, and 6.
- Strong ReAct with replanning and failure classification is covered by Task 5.
- Event trail and replay are covered by Tasks 2 and 6.
- Frontend runtime exposure is covered by Task 7.
- Legacy AI control consolidation is covered by Task 8.

### Placeholder scan

- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Every task includes exact file paths, exact commands, and at least one concrete code block.

### Type consistency

- `GoalSpec`, `ExecutionPlan`, `CapabilityDefinition`, `GoalRuntimeService`, and the session/event route names are used consistently across tasks.
- API route prefix stays `/api/agent-runtime` across backend and frontend tasks.
- Permission modes remain `high | low` everywhere.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-09-platform-goal-runtime-agent.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
