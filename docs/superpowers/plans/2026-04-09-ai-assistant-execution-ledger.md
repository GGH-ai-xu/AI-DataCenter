# AI 助手执行账本重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 AI 助手“执行控制”页重构为左侧控制台 + 右侧调试级执行账本，并让 runtime 真实记录每次 LLM 调用、计划、审批、执行和失败事件。

**Architecture:** 后端先把 goal runtime 的事件模型从粗粒度 session 事件升级为可排序、可分轮次的 rich event stream，再在 service/api 层导出适合 UI 使用的 session view。前端在 `AIAssistant.vue` 外围引入独立的账本派生 helper 和组件树，右侧账本基于事件流渲染 overview、round 和 event card，默认展示摘要，按需展开 prompt / response / arguments / error。

**Tech Stack:** FastAPI, Python, SQLite, Vue 3, node:test, Vite, repository-level Python structure tests

---

## File Structure

### Backend

- Modify: `backend/app/services/goal_runtime/data_store_support.py`
  Purpose: 为 runtime event 表增加 `round_index / sequence / source / duration_ms` 等字段，并统一事件序列化/反序列化。
- Modify: `backend/app/services/data_store.py`
  Purpose: 暴露 richer `append_agent_event()` / `get_agent_events()` 包装层。
- Create: `backend/app/services/goal_runtime/reasoning_trace.py`
  Purpose: 统一封装“采集上下文 -> 调 LLM 或规则解析 -> 生成 planning 事件”的可观测推理链。
- Create: `backend/app/services/goal_runtime/session_view.py`
  Purpose: 从 session + events 派生 UI 所需的 `pending_approval / latest_error / llm_call_count / event_count / current_round`。
- Modify: `backend/app/services/goal_runtime/service.py`
  Purpose: 接入 richer 事件写入、LLM service reader 和 session view。
- Modify: `backend/app/services/goal_runtime/supervisor.py`
  Purpose: 为执行步骤、失败和重规划写入 richer event metadata。
- Modify: `backend/app/services/goal_runtime/goal_parser.py`
  Purpose: 保持 GoalSpec 生成职责，但不再承担完整推理链。
- Modify: `backend/app/api/agent_runtime.py`
  Purpose: session 接口返回 session view，events 接口返回 richer event payload。
- Modify: `backend/app/main.py`
  Purpose: 给 `GoalRuntimeService` 注入 LLM service reader。

### Frontend

- Create: `frontend/src/lib/agentExecutionLedger.js`
  Purpose: 纯函数派生 `groupedRounds / highlightedEvents / overview / tone / preview blocks`。
- Create: `frontend/src/lib/agentExecutionLedger.test.js`
  Purpose: 账本派生逻辑回归。
- Create: `frontend/src/lib/agentRuntimeSessionPolling.js`
  Purpose: 独立的 session polling controller，控制 `2s` 轮询与终态停止。
- Create: `frontend/src/lib/agentRuntimeSessionPolling.test.js`
  Purpose: 轮询行为回归。
- Create: `frontend/src/components/agent/AgentControlDock.vue`
  Purpose: 左侧输入、权限、风险确认、会话摘要和审批动作。
- Create: `frontend/src/components/agent/AgentExecutionLedger.vue`
  Purpose: 右侧账本总容器。
- Create: `frontend/src/components/agent/AgentRunOverviewBar.vue`
  Purpose: 账本顶部 overview 条。
- Create: `frontend/src/components/agent/AgentLedgerRound.vue`
  Purpose: 单轮事件组。
- Create: `frontend/src/components/agent/AgentLedgerEventCard.vue`
  Purpose: 事件卡摘要/展开详情。
- Modify: `frontend/src/views/AIAssistant.vue`
  Purpose: 改为页面级 orchestrator，只拼装 control dock、ledger 和 chat/model tab。
- Modify: `tests/test_frontend_ui_structure.py`
  Purpose: 锁定新组件结构与旧 timeline 不再作为主展示。

### Tests

- Modify: `tests/test_goal_runtime_data_store.py`
- Modify: `tests/test_goal_runtime_supervisor.py`
- Modify: `tests/test_goal_runtime_api.py`
- Modify: `backend/tests/test_ai_control.py`
- Modify: `tests/test_real_data_only_structure.py`

---

### Task 1: Persist Rich Runtime Event Metadata

**Files:**
- Modify: `backend/app/services/goal_runtime/data_store_support.py`
- Modify: `backend/app/services/data_store.py`
- Modify: `tests/test_goal_runtime_data_store.py`

- [ ] **Step 1: Write the failing data-store regression test**

Add this test to `tests/test_goal_runtime_data_store.py`:

```python
async def test_append_agent_event_persists_round_sequence_source_and_duration(self):
    store = await self.build_store()
    await store.create_agent_session(
        "sess-1",
        {"message": "把 GPU 0 的功耗上限调到 220W"},
        "low",
        "running",
        "把 GPU 0 的功耗上限调到 220W",
    )

    await store.append_agent_event(
        "sess-1",
        "LLMRequestPrepared",
        {"summary": "准备调用 LLM", "prompt_preview": "用户指令..."},
        round_index=1,
        sequence=2,
        source="llm",
        duration_ms=35,
    )

    events = await store.get_agent_events("sess-1")
    self.assertEqual(events[0]["round_index"], 1)
    self.assertEqual(events[0]["sequence"], 2)
    self.assertEqual(events[0]["source"], "llm")
    self.assertEqual(events[0]["duration_ms"], 35)
    self.assertEqual(events[0]["payload"]["prompt_preview"], "用户指令...")
```

- [ ] **Step 2: Run the targeted test and verify it fails**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m pytest tests/test_goal_runtime_data_store.py -q
```

Expected: FAIL with `TypeError` for unexpected keyword arguments on `append_agent_event()` or missing event columns in normalized rows.

- [ ] **Step 3: Implement the minimal schema and wrapper changes**

Update `backend/app/services/goal_runtime/data_store_support.py` so event storage includes the new metadata:

```python
CREATE TABLE IF NOT EXISTS agent_runtime_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    round_index INTEGER NOT NULL DEFAULT 0,
    sequence INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'runtime',
    duration_ms INTEGER NOT NULL DEFAULT 0,
    timestamp REAL NOT NULL
);
```

Update the helpers:

```python
async def append_agent_event(
    connection: aiosqlite.Connection,
    session_id: str,
    event_type: str,
    payload: dict,
    *,
    round_index: int = 0,
    sequence: int = 0,
    source: str = "runtime",
    duration_ms: int = 0,
) -> None:
    await connection.execute(
        """INSERT INTO agent_runtime_events
           (session_id, event_type, payload_json, round_index, sequence, source, duration_ms, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            session_id,
            event_type,
            json.dumps(payload, ensure_ascii=False),
            round_index,
            sequence,
            source,
            duration_ms,
            time.time(),
        ),
    )
```

Update `backend/app/services/data_store.py` to pass through the same keyword-only arguments:

```python
async def append_agent_event(
    self,
    session_id: str,
    event_type: str,
    payload: dict,
    *,
    round_index: int = 0,
    sequence: int = 0,
    source: str = "runtime",
    duration_ms: int = 0,
) -> None:
    await append_runtime_event(
        require_runtime_db(self._db),
        session_id,
        event_type,
        payload,
        round_index=round_index,
        sequence=sequence,
        source=source,
        duration_ms=duration_ms,
    )
```

- [ ] **Step 4: Run the test again and verify it passes**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m pytest tests/test_goal_runtime_data_store.py -q
```

Expected: PASS with the new metadata persisted and returned from `get_agent_events()`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/goal_runtime/data_store_support.py backend/app/services/data_store.py tests/test_goal_runtime_data_store.py
git commit -m "feat: persist rich goal runtime event metadata"
```

---

### Task 2: Add LLM-Aware Reasoning Trace Events

**Files:**
- Create: `backend/app/services/goal_runtime/reasoning_trace.py`
- Modify: `backend/app/services/goal_runtime/service.py`
- Modify: `backend/app/services/goal_runtime/goal_parser.py`
- Modify: `backend/app/main.py`
- Modify: `tests/test_goal_runtime_supervisor.py`
- Modify: `backend/tests/test_ai_control.py`

- [ ] **Step 1: Write the failing runtime trace tests**

Extend `tests/test_goal_runtime_supervisor.py` with both LLM and non-LLM paths:

```python
async def test_start_session_emits_llm_trace_events_when_llm_available(self):
    runtime = build_runtime_service(llm=FakeLLM({
        "summary": "计划限制 GPU 0 功耗并等待审批",
        "risk_level": "medium",
        "requires_confirmation": True,
        "warnings": [],
        "actions": [{"action": "set_power_limit", "target": {"gpu_index": 0, "power_limit": 220}, "reason": "削峰"}],
    }))

    result = await runtime.start_session("把 GPU 0 的功耗上限调到 220W", "low")
    events = await runtime.get_events(result["session_id"])
    event_types = [item["event_type"] for item in events]

    self.assertIn("ContextSnapshotCaptured", event_types)
    self.assertIn("LLMRequestPrepared", event_types)
    self.assertIn("LLMResponseReceived", event_types)
    self.assertIn("LLMPlanExtracted", event_types)
```

```python
async def test_start_session_emits_explicit_rule_fallback_when_llm_unavailable(self):
    runtime = build_runtime_service(llm=None)

    result = await runtime.start_session("执行一次调度", "high")
    events = await runtime.get_events(result["session_id"])
    event_types = [item["event_type"] for item in events]

    self.assertIn("LLMUnavailable", event_types)
    self.assertIn("RuleFallbackUsed", event_types)
```

Also add a focused heuristic test in `backend/tests/test_ai_control.py` to confirm `build_control_heuristic()` still produces the same action names used by the runtime trace path.

- [ ] **Step 2: Run the targeted tests and verify they fail**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m pytest tests/test_goal_runtime_supervisor.py backend/tests/test_ai_control.py -q
```

Expected: FAIL because the runtime currently never emits `ContextSnapshotCaptured`, `LLMRequestPrepared`, `LLMResponseReceived`, `LLMPlanExtracted`, `LLMUnavailable`, or `RuleFallbackUsed`.

- [ ] **Step 3: Implement the reasoning trace helper and service wiring**

Create `backend/app/services/goal_runtime/reasoning_trace.py`:

```python
from app.services.goal_runtime.control_heuristics import build_control_heuristic
from app.services.goal_runtime.executor import execute_capability


async def build_reasoning_trace(
    *,
    session_id: str,
    message: str,
    permission_mode: str,
    registry,
    llm_service,
) -> tuple[dict, list[dict]]:
    snapshot_result = await execute_capability(registry, "runtime.snapshot.read", {}, {})
    snapshot = snapshot_result["output"] if snapshot_result["success"] else {}
    events = [{
        "event_type": "ContextSnapshotCaptured",
        "payload": {"summary": "已采集当前运行时快照", "snapshot_preview": snapshot},
        "round_index": 1,
        "sequence": 1,
        "source": "planner",
    }]

    if llm_service is None:
        heuristic = build_control_heuristic(message)
        events.extend([
            {"event_type": "LLMUnavailable", "payload": {"summary": "当前未配置 LLM，切换到规则解析"}, "round_index": 1, "sequence": 2, "source": "llm"},
            {"event_type": "RuleFallbackUsed", "payload": {"summary": heuristic["summary"], "actions": heuristic["actions"]}, "round_index": 1, "sequence": 3, "source": "planner"},
        ])
        return heuristic, events

    control_context = {"snapshot": snapshot, "message": message, "permission_mode": permission_mode}
    events.append({
        "event_type": "LLMRequestPrepared",
        "payload": {"summary": "准备生成结构化动作计划", "prompt_preview": str(control_context)[:240]},
        "round_index": 1,
        "sequence": 2,
        "source": "llm",
    })
    llm_plan = await llm_service.generate_control_plan(message, str(control_context))
    events.append({
        "event_type": "LLMResponseReceived",
        "payload": {"summary": llm_plan["summary"], "response_preview": str(llm_plan)[:320], "response_full": llm_plan},
        "round_index": 1,
        "sequence": 3,
        "source": "llm",
    })
    events.append({
        "event_type": "LLMPlanExtracted",
        "payload": {"summary": llm_plan["summary"], "structured_plan": llm_plan},
        "round_index": 1,
        "sequence": 4,
        "source": "planner",
    })
    return llm_plan, events
```

Update `backend/app/services/goal_runtime/service.py` to accept an LLM reader and append these events before `PlanCreated`:

```python
class GoalRuntimeService:
    def __init__(self, store, registry, import_context, runtime_status_reader, llm_service_reader):
        self.llm_service_reader = llm_service_reader
```

```python
planner_result, trace_events = await build_reasoning_trace(
    session_id=session_id,
    message=message,
    permission_mode=permission_mode,
    registry=self.registry,
    llm_service=self.llm_service_reader(),
)
for event in trace_events:
    await self.append_event(
        session_id,
        event["event_type"],
        event["payload"],
        round_index=event["round_index"],
        sequence=event["sequence"],
        source=event["source"],
    )
```

Update `backend/app/main.py` to inject `llm_service_reader=lambda: app_state.llm`.

- [ ] **Step 4: Run the targeted tests again and verify they pass**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m pytest tests/test_goal_runtime_supervisor.py backend/tests/test_ai_control.py -q
```

Expected: PASS with explicit LLM/rule-path trace events written to the session.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/goal_runtime/reasoning_trace.py backend/app/services/goal_runtime/service.py backend/app/services/goal_runtime/goal_parser.py backend/app/main.py tests/test_goal_runtime_supervisor.py backend/tests/test_ai_control.py
git commit -m "feat: trace goal runtime reasoning and llm events"
```

---

### Task 3: Expose a Ledger-Friendly Session View

**Files:**
- Create: `backend/app/services/goal_runtime/session_view.py`
- Modify: `backend/app/services/goal_runtime/service.py`
- Modify: `backend/app/api/agent_runtime.py`
- Modify: `tests/test_goal_runtime_api.py`

- [ ] **Step 1: Write the failing API/session view test**

Extend `tests/test_goal_runtime_api.py`:

```python
async def test_get_session_returns_derived_ledger_summary_fields(self):
    store = FakeStore()
    runtime = GoalRuntimeService(
        store=store,
        registry=build_registry(),
        import_context=FakeImportContext(),
        runtime_status_reader=None,
        llm_service_reader=lambda: None,
    )
    started = await runtime.start_session("把 GPU 0 的功耗上限调到 220W", "low")
    session = await runtime.get_session(started["session_id"])

    self.assertIn("event_count", session)
    self.assertIn("current_round", session)
    self.assertIn("llm_call_count", session)
    self.assertIn("awaiting_approval", session)
    self.assertIn("pending_approval", session)
```

Also update the route-level fake runtime assertion:

```python
self.assertIn("event_count", session)
self.assertIn("awaiting_approval", session)
```

- [ ] **Step 2: Run the API test and verify it fails**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m pytest tests/test_goal_runtime_api.py -q
```

Expected: FAIL because `GoalRuntimeService.get_session()` still returns the raw DB row without any ledger-derived fields.

- [ ] **Step 3: Implement a dedicated session view builder**

Create `backend/app/services/goal_runtime/session_view.py`:

```python
def build_session_view(session: dict, events: list[dict]) -> dict:
    pending_approval = None
    latest_error = ""
    current_round = 0
    llm_call_count = 0

    for event in events:
        current_round = max(current_round, int(event.get("round_index") or 0))
        if event.get("event_type") == "LLMResponseReceived":
            llm_call_count += 1
        if event.get("event_type") == "AwaitingApproval":
            pending_approval = event.get("payload")
        if event.get("event_type") in {"StepFailed", "SessionFailed", "LLMCallFailed"}:
            latest_error = event.get("payload", {}).get("error", latest_error)

    return {
        **session,
        "event_count": len(events),
        "current_round": current_round,
        "llm_call_count": llm_call_count,
        "awaiting_approval": session.get("status") == "awaiting_approval",
        "pending_approval": pending_approval,
        "latest_error": latest_error,
    }
```

Update `backend/app/services/goal_runtime/service.py`:

```python
async def get_session(self, session_id: str) -> dict | None:
    session = await self.store.get_agent_session(session_id)
    if session is None:
        return None
    events = await self.store.get_agent_events(session_id)
    return build_session_view(session, events)
```

Leave `get_events()` returning the raw event list so the UI can build its own grouped rounds.

- [ ] **Step 4: Run the API test again and verify it passes**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m pytest tests/test_goal_runtime_api.py -q
```

Expected: PASS with session endpoints returning derived ledger summary fields.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/goal_runtime/session_view.py backend/app/services/goal_runtime/service.py backend/app/api/agent_runtime.py tests/test_goal_runtime_api.py
git commit -m "feat: expose ledger-friendly goal runtime session view"
```

---

### Task 4: Build Frontend Ledger Derivation and Polling Helpers

**Files:**
- Create: `frontend/src/lib/agentExecutionLedger.js`
- Create: `frontend/src/lib/agentExecutionLedger.test.js`
- Create: `frontend/src/lib/agentRuntimeSessionPolling.js`
- Create: `frontend/src/lib/agentRuntimeSessionPolling.test.js`

- [ ] **Step 1: Write the failing frontend helper tests**

Create `frontend/src/lib/agentExecutionLedger.test.js`:

```javascript
import test from 'node:test'
import assert from 'node:assert/strict'
import { buildExecutionLedgerView } from './agentExecutionLedger.js'

test('buildExecutionLedgerView groups events by round and highlights critical cards', () => {
  const view = buildExecutionLedgerView({
    session: { session_id: 'sess-1', status: 'awaiting_approval' },
    events: [
      { event_type: 'LLMRequestPrepared', round_index: 1, sequence: 1, timestamp: 1, source: 'llm', payload: { summary: '准备请求' } },
      { event_type: 'LLMResponseReceived', round_index: 1, sequence: 2, timestamp: 2, source: 'llm', payload: { summary: '给出计划', response_preview: '...' } },
      { event_type: 'AwaitingApproval', round_index: 1, sequence: 3, timestamp: 3, source: 'approval', payload: { actions: [{ capability_name: 'scheduler.power_limit.set' }] } },
    ],
  })

  assert.equal(view.overview.llmCallCount, 1)
  assert.equal(view.rounds.length, 1)
  assert.equal(view.rounds[0].events[1].tone, 'llm')
  assert.equal(view.highlightedEvents[0].eventType, 'AwaitingApproval')
})
```

Create `frontend/src/lib/agentRuntimeSessionPolling.test.js`:

```javascript
import test from 'node:test'
import assert from 'node:assert/strict'
import { createAgentRuntimeSessionPolling } from './agentRuntimeSessionPolling.js'

test('polling stops when session reaches terminal state', async () => {
  let active = 0
  const calls = []
  const scheduler = {
    setInterval(fn) { active += 1; calls.push(fn); return 'timer-1' },
    clearInterval(id) { active -= 1; assert.equal(id, 'timer-1') },
  }
  const polling = createAgentRuntimeSessionPolling({ scheduler, intervalMs: 2000 })
  polling.start(() => Promise.resolve({ status: 'completed' }))
  await calls[0]()
  assert.equal(active, 0)
})
```

- [ ] **Step 2: Run the helper tests and verify they fail**

Run:

```bash
node --test frontend/src/lib/agentExecutionLedger.test.js frontend/src/lib/agentRuntimeSessionPolling.test.js
```

Expected: FAIL because neither helper exists yet.

- [ ] **Step 3: Implement the pure helpers**

Create `frontend/src/lib/agentExecutionLedger.js`:

```javascript
const HIGHLIGHT_EVENT_TYPES = new Set([
  'LLMResponseReceived',
  'AwaitingApproval',
  'PlanRevised',
  'StepFailed',
  'SessionFailed',
  'SessionCompleted',
])

export function buildExecutionLedgerView({ session, events }) {
  const sorted = [...(events || [])].sort((a, b) => (
    (a.round_index - b.round_index)
    || (a.sequence - b.sequence)
    || (a.timestamp - b.timestamp)
  ))
  const rounds = []
  const roundMap = new Map()
  let llmCallCount = 0

  for (const event of sorted) {
    if (event.event_type === 'LLMResponseReceived') llmCallCount += 1
    const roundIndex = Number(event.round_index || 0)
    if (!roundMap.has(roundIndex)) {
      roundMap.set(roundIndex, { roundIndex, events: [] })
      rounds.push(roundMap.get(roundIndex))
    }
    roundMap.get(roundIndex).events.push({
      eventType: event.event_type,
      tone: mapEventTone(event.event_type),
      summary: event.payload?.summary || event.payload?.error || event.event_type,
      details: event.payload || {},
      timestamp: event.timestamp,
      sequence: event.sequence,
    })
  }

  return {
    overview: {
      status: session?.status || 'idle',
      eventCount: sorted.length,
      llmCallCount,
      currentRound: rounds.at(-1)?.roundIndex || 0,
      awaitingApproval: session?.awaiting_approval || false,
      latestError: session?.latest_error || '',
    },
    rounds,
    highlightedEvents: sorted
      .filter((event) => HIGHLIGHT_EVENT_TYPES.has(event.event_type))
      .map((event) => ({ eventType: event.event_type, payload: event.payload || {} })),
  }
}
```

Create `frontend/src/lib/agentRuntimeSessionPolling.js`:

```javascript
export function createAgentRuntimeSessionPolling({ scheduler = globalThis, intervalMs = 2000 } = {}) {
  let timerId = null

  function stop() {
    if (!timerId) return
    scheduler.clearInterval(timerId)
    timerId = null
  }

  function start(refresh) {
    stop()
    timerId = scheduler.setInterval(async () => {
      const session = await refresh()
      if (['completed', 'failed', 'aborted'].includes(session?.status)) {
        stop()
      }
    }, intervalMs)
  }

  return { start, stop }
}
```

- [ ] **Step 4: Run the helper tests again and verify they pass**

Run:

```bash
node --test frontend/src/lib/agentExecutionLedger.test.js frontend/src/lib/agentRuntimeSessionPolling.test.js
```

Expected: PASS with grouped rounds, highlighted events and terminal-state polling stop behavior verified.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/agentExecutionLedger.js frontend/src/lib/agentExecutionLedger.test.js frontend/src/lib/agentRuntimeSessionPolling.js frontend/src/lib/agentRuntimeSessionPolling.test.js
git commit -m "feat: add agent execution ledger frontend helpers"
```

---

### Task 5: Integrate the New Ledger UI Into AIAssistant

**Files:**
- Create: `frontend/src/components/agent/AgentControlDock.vue`
- Create: `frontend/src/components/agent/AgentExecutionLedger.vue`
- Create: `frontend/src/components/agent/AgentRunOverviewBar.vue`
- Create: `frontend/src/components/agent/AgentLedgerRound.vue`
- Create: `frontend/src/components/agent/AgentLedgerEventCard.vue`
- Modify: `frontend/src/views/AIAssistant.vue`
- Modify: `tests/test_frontend_ui_structure.py`
- Modify: `tests/test_real_data_only_structure.py`

- [ ] **Step 1: Write the failing structure tests**

Extend `tests/test_frontend_ui_structure.py`:

```python
def test_ai_assistant_uses_execution_ledger_components(self):
    text = (ROOT / "frontend/src/views/AIAssistant.vue").read_text(encoding="utf-8")
    self.assertIn("AgentControlDock", text)
    self.assertIn("AgentExecutionLedger", text)
    self.assertNotIn("AgentSessionTimeline", text)

    for rel in [
        "frontend/src/components/agent/AgentControlDock.vue",
        "frontend/src/components/agent/AgentExecutionLedger.vue",
        "frontend/src/components/agent/AgentRunOverviewBar.vue",
        "frontend/src/components/agent/AgentLedgerRound.vue",
        "frontend/src/components/agent/AgentLedgerEventCard.vue",
    ]:
        self.assertTrue((ROOT / rel).exists(), rel)
```

Extend `tests/test_real_data_only_structure.py`:

```python
def test_ai_assistant_no_longer_uses_legacy_timeline_as_primary_execution_view(self):
    text = (ROOT / "frontend/src/views/AIAssistant.vue").read_text(encoding="utf-8")
    self.assertNotIn("Session Timeline", text)
    self.assertIn("AgentExecutionLedger", text)
```

- [ ] **Step 2: Run the structure tests and verify they fail**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure tests.test_real_data_only_structure -q
```

Expected: FAIL because the new ledger components do not exist and `AIAssistant.vue` still renders the old inline execution area.

- [ ] **Step 3: Implement the component tree and page integration**

Create `frontend/src/components/agent/AgentRunOverviewBar.vue`:

```vue
<script setup>
defineProps({
  overview: { type: Object, required: true },
})
</script>

<template>
  <header class="agent-run-overview">
    <div class="agent-run-overview__title">Execution Ledger</div>
    <div class="agent-run-overview__facts">
      <span>{{ overview.status }}</span>
      <span>{{ overview.eventCount }} 事件</span>
      <span>{{ overview.llmCallCount }} 次 LLM</span>
      <span v-if="overview.awaitingApproval">等待审批</span>
      <span v-if="overview.latestError">{{ overview.latestError }}</span>
    </div>
  </header>
</template>
```

Create `frontend/src/components/agent/AgentLedgerEventCard.vue` with summary + details disclosure:

```vue
<script setup>
import { ref } from 'vue'
const expanded = ref(false)
const props = defineProps({
  event: { type: Object, required: true },
})
</script>

<template>
  <article class="agent-ledger-event-card" :data-tone="event.tone">
    <button type="button" class="agent-ledger-event-card__summary" @click="expanded = !expanded">
      <strong>{{ event.eventType }}</strong>
      <span>{{ event.summary }}</span>
    </button>
    <pre v-if="expanded" class="agent-ledger-event-card__details">{{ JSON.stringify(event.details, null, 2) }}</pre>
  </article>
</template>
```

Create `frontend/src/components/agent/AgentExecutionLedger.vue`:

```vue
<script setup>
import AgentRunOverviewBar from './AgentRunOverviewBar.vue'
import AgentLedgerRound from './AgentLedgerRound.vue'

defineProps({
  overview: { type: Object, required: true },
  rounds: { type: Array, default: () => [] },
  highlightedEvents: { type: Array, default: () => [] },
  refreshError: { type: String, default: '' },
})
</script>

<template>
  <section class="agent-execution-ledger tech-card">
    <AgentRunOverviewBar :overview="overview" />
    <div v-if="refreshError" class="agent-execution-ledger__error">{{ refreshError }}</div>
    <AgentLedgerRound
      v-for="round in rounds"
      :key="round.roundIndex"
      :round="round"
      :highlighted-events="highlightedEvents"
    />
  </section>
</template>
```

Modify `frontend/src/views/AIAssistant.vue` so the control tab becomes orchestration only:

```vue
<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import AgentControlDock from '../components/agent/AgentControlDock.vue'
import AgentExecutionLedger from '../components/agent/AgentExecutionLedger.vue'
import { buildExecutionLedgerView } from '../lib/agentExecutionLedger.js'
import { createAgentRuntimeSessionPolling } from '../lib/agentRuntimeSessionPolling.js'
```

```vue
<template>
  <section v-else-if="activeTab === 'control'" class="ai-runtime-workbench">
    <AgentControlDock
      :permission-mode="controlPermissionMode"
      :risk-acknowledged="controlRiskAcknowledged"
      :runtime-session="runtimeSession"
      :pending-approval-actions="pendingApprovalActions"
      :planning="controlPlanning"
      :executing="controlExecuting"
      @submit="generateControlPlan"
      @approve="executeControlPlan"
    />
    <AgentExecutionLedger
      :overview="ledgerView.overview"
      :rounds="ledgerView.rounds"
      :highlighted-events="ledgerView.highlightedEvents"
      :refresh-error="ledgerRefreshError"
    />
  </section>
</template>
```

Use the polling helper so only the active runtime session refreshes every 2 seconds while `running` or `awaiting_approval`.

- [ ] **Step 4: Run the structure tests, helper tests and build**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure tests.test_real_data_only_structure -q
node --test frontend/src/lib/agentExecutionLedger.test.js frontend/src/lib/agentRuntimeSessionPolling.test.js
npm --prefix frontend run build
```

Expected: PASS with the new component tree wired in and the production build succeeding.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/agent/AgentControlDock.vue frontend/src/components/agent/AgentExecutionLedger.vue frontend/src/components/agent/AgentRunOverviewBar.vue frontend/src/components/agent/AgentLedgerRound.vue frontend/src/components/agent/AgentLedgerEventCard.vue frontend/src/views/AIAssistant.vue frontend/src/lib/agentExecutionLedger.js frontend/src/lib/agentExecutionLedger.test.js frontend/src/lib/agentRuntimeSessionPolling.js frontend/src/lib/agentRuntimeSessionPolling.test.js tests/test_frontend_ui_structure.py tests/test_real_data_only_structure.py
git commit -m "feat: add ai assistant execution ledger ui"
```

---

### Task 6: Run Full Verification And Cleanly Land The Refactor

**Files:**
- Modify: `tests/test_goal_runtime_api.py`
- Modify: `tests/test_goal_runtime_supervisor.py`
- Modify: `tests/test_goal_runtime_data_store.py`
- Modify: `backend/tests/test_ai_control.py`
- Modify: `tests/test_frontend_ui_structure.py`
- Modify: `tests/test_real_data_only_structure.py`

- [ ] **Step 1: Run the full targeted backend regression suite**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m pytest tests/test_goal_runtime_models.py tests/test_goal_runtime_data_store.py tests/test_goal_runtime_capabilities.py tests/test_goal_runtime_planner.py tests/test_goal_runtime_supervisor.py tests/test_goal_runtime_api.py backend/tests/test_ai_control.py tests/test_scheduler.py tests/test_runtime_snapshot_routes.py -q
```

Expected: PASS with the richer event stream and runtime session view still compatible with the existing goal runtime feature set.

- [ ] **Step 2: Run the structure and frontend helper suites**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure tests.test_real_data_only_structure -q
node --test frontend/src/lib/agentExecutionLedger.test.js frontend/src/lib/agentRuntimeSessionPolling.test.js
```

Expected: PASS with the new component tree and helper logic verified.

- [ ] **Step 3: Run compile/build verification**

Run:

```bash
./.venv/Scripts/python.exe -m compileall backend/app
npm --prefix frontend run build
```

Expected: PASS with no import breakage and a successful production build.

- [ ] **Step 4: Update push log after implementation**

Append one new entry to `push日志.txt` summarizing:

```text
发现的问题：AI 助手执行控制区仍然无法可视化 agent 的完整执行过程，只能看到简化 timeline，无法查看每步 LLM 调用、审批和失败细节。
解决方法：补齐 goal runtime 的 rich event stream、session view、前端 execution ledger 组件树与 polling 机制，并以事件卡形式展示 prompt / response / arguments / error。
```

- [ ] **Step 5: Commit the final integrated refactor**

```bash
git add backend/app/main.py backend/app/api/agent_runtime.py backend/app/services/goal_runtime/*.py backend/app/services/data_store.py tests/test_goal_runtime_*.py backend/tests/test_ai_control.py frontend/src/components/agent/*.vue frontend/src/lib/agentExecutionLedger.js frontend/src/lib/agentExecutionLedger.test.js frontend/src/lib/agentRuntimeSessionPolling.js frontend/src/lib/agentRuntimeSessionPolling.test.js frontend/src/views/AIAssistant.vue tests/test_frontend_ui_structure.py tests/test_real_data_only_structure.py push日志.txt
git commit -m "feat: visualize ai assistant execution ledger"
```

---

## Self-Review

### Spec Coverage

- 双栏布局：Task 5 covers `AgentControlDock` + `AgentExecutionLedger`.
- 调试级执行账本：Task 4 and Task 5 cover round grouping, overview and event cards.
- 每步 LLM 调用事件：Task 2 covers `LLMRequestPrepared / LLMResponseReceived / LLMPlanExtracted / LLMUnavailable / RuleFallbackUsed`.
- 默认摘要、展开详情：Task 5 covers `AgentLedgerEventCard.vue`.
- richer session view / approval / latest error：Task 3 covers derived session fields.
- 刷新策略：Task 4 and Task 5 cover polling start/stop and terminal-state behavior.
- 失败可见、不静默 fallback：Task 2 and Task 6 cover explicit failure/fallback events plus regression checks.

No uncovered spec sections remain.

### Placeholder Scan

- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Each task includes exact file paths, code snippets, commands and expected outcomes.

### Type Consistency

- Backend event metadata uses `round_index`, `sequence`, `source`, `duration_ms` consistently across persistence, service and tests.
- Frontend ledger helper expects the same `round_index`, `sequence`, `source` fields as the backend emits.
- Session summary naming is consistent: `event_count`, `current_round`, `llm_call_count`, `awaiting_approval`, `pending_approval`, `latest_error`.
