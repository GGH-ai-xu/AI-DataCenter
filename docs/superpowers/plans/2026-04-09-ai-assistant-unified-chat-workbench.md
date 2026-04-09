# AI 助手统一聊天工作台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `AIAssistant.vue` 从“执行控制 + 对话解释 + 模型配置”三页结构重构为“统一聊天工作台 + 模型配置”两页结构，并在一个聊天线程内承载问答、计划、审批、工具调用、结果和错误。

**Architecture:** 前端保留现有 `chat stream` 与 `runtime session` 双通道，但新增统一线程模型，将两类消息都归并为 `AgentThreadItem` 渲染到同一条工作台消息流。后端仅补一个轻量的 session 列表接口，支撑左侧紧凑会话栏；其余执行细节继续使用现有 runtime 事件流与 SSE 通道。

**Tech Stack:** Vue 3, Vite, node:test, FastAPI, SQLite, Python `unittest`, existing SSE stream helpers

---

## File Structure

### Backend

- Modify: `backend/app/services/goal_runtime/data_store_support.py`
  - 增加 session 列表查询，按 `updated_at DESC` 返回紧凑会话记录。
- Modify: `backend/app/services/data_store.py`
  - 暴露 `list_agent_sessions()`。
- Modify: `backend/app/services/goal_runtime/service.py`
  - 暴露 `list_sessions()`，供 API 使用。
- Modify: `backend/app/api/agent_runtime.py`
  - 新增 `GET /api/agent-runtime/sessions`。
- Modify: `tests/test_goal_runtime_data_store.py`
  - 锁定会话列表排序与字段。
- Modify: `tests/test_goal_runtime_api.py`
  - 锁定列表接口返回结构。

### Frontend Lib

- Create: `frontend/src/lib/agentSessionHistory.js`
  - 将后端 session 列表转换为左侧紧凑会话栏项。
- Create: `frontend/src/lib/agentSessionHistory.test.js`
  - 回归会话标题、状态和时间格式。
- Create: `frontend/src/lib/agentWorkbenchThread.js`
  - 将 chat 消息、runtime 事件、session 状态转换为统一线程项与顶部状态条数据。
- Create: `frontend/src/lib/agentWorkbenchThread.test.js`
  - 回归计划卡、审批卡、工具调用卡、错误卡的生成规则。
- Create: `frontend/src/lib/agentWorkbenchIntent.js`
  - 统一输入的路由判断：`chat`、`runtime` 或 `confirm`。
- Create: `frontend/src/lib/agentWorkbenchIntent.test.js`
  - 回归显式问答、显式执行与模糊输入确认。

### Frontend Components

- Create: `frontend/src/components/agent/AgentWorkbench.vue`
  - 工作台主布局，拼接左栏、顶部条、线程和输入区。
- Create: `frontend/src/components/agent/AgentSessionRail.vue`
  - 左侧紧凑会话列表。
- Create: `frontend/src/components/agent/AgentWorkbenchTopbar.vue`
  - 顶部薄状态条。
- Create: `frontend/src/components/agent/AgentThread.vue`
  - 统一线程容器。
- Create: `frontend/src/components/agent/AgentThreadItem.vue`
  - 分发不同 `kind` 的线程项。
- Create: `frontend/src/components/agent/AgentThreadMessage.vue`
  - 用户/助手普通消息，复用 `AgentChatMessageBody.vue`。
- Create: `frontend/src/components/agent/AgentThreadPlanCard.vue`
  - 紧凑计划卡。
- Create: `frontend/src/components/agent/AgentThreadApprovalCard.vue`
  - 线程内审批卡。
- Create: `frontend/src/components/agent/AgentThreadToolEventCard.vue`
  - 默认折叠单行的工具调用卡。
- Create: `frontend/src/components/agent/AgentThreadResultCard.vue`
  - 结果卡。
- Create: `frontend/src/components/agent/AgentThreadErrorCard.vue`
  - 错误卡。
- Create: `frontend/src/components/agent/AgentThreadRouteConfirmCard.vue`
  - 模糊输入时的线程内路由确认卡。
- Create: `frontend/src/components/agent/AgentComposer.vue`
  - 底部固定输入区与建议 chips。

### Frontend View / API

- Modify: `frontend/src/views/AIAssistant.vue`
  - 重构为 `workbench` / `model` 两页。
- Modify: `frontend/src/services/api.js`
  - 新增 `getAgentRuntimeSessions()`。

### Structure / Regression Tests

- Modify: `tests/test_frontend_ui_structure.py`
  - 从旧的 `AgentControlDock / AgentExecutionLedger` 约束切到新工作台结构。
- Modify: `tests/test_real_data_only_structure.py`
  - 删除旧账本组件要求，改为统一工作台约束。

---

### Task 1: Add Compact Runtime Session History API

**Files:**
- Modify: `backend/app/services/goal_runtime/data_store_support.py`
- Modify: `backend/app/services/data_store.py`
- Modify: `backend/app/services/goal_runtime/service.py`
- Modify: `backend/app/api/agent_runtime.py`
- Modify: `frontend/src/services/api.js`
- Modify: `tests/test_goal_runtime_data_store.py`
- Modify: `tests/test_goal_runtime_api.py`

- [ ] **Step 1: Write the failing data-store and API tests**

Add this test to `tests/test_goal_runtime_data_store.py`:

```python
async def test_list_agent_sessions_returns_latest_first(self):
    with tempfile.TemporaryDirectory() as tmpdir:
        store = DataStore(os.path.join(tmpdir, "runtime.db"))
        await store.init()
        try:
            await store.create_agent_session(
                "sess-older",
                {"message": "先前会话"},
                "low",
                "completed",
                "先前会话",
            )
            await store.create_agent_session(
                "sess-latest",
                {"message": "最新会话"},
                "high",
                "running",
                "最新会话",
            )
            await store.update_agent_session_status(
                "sess-latest",
                "awaiting_approval",
                "最新会话",
                live_phase="awaiting_approval",
            )

            sessions = await store.list_agent_sessions(limit=10)
        finally:
            await store.close()

    self.assertEqual(sessions[0]["session_id"], "sess-latest")
    self.assertEqual(sessions[0]["status"], "awaiting_approval")
    self.assertEqual(sessions[1]["session_id"], "sess-older")
```

Extend the route import in `tests/test_goal_runtime_api.py`:

```python
from app.api.agent_runtime import (
    approve_agent_runtime_session,
    get_agent_runtime_events,
    get_agent_runtime_session,
    list_agent_runtime_sessions,
    start_agent_runtime_session,
    stream_agent_runtime_session,
)
```

Add this method to the existing `FakeGoalRuntimeService` in `tests/test_goal_runtime_api.py`:

```python
    async def list_sessions(self, limit=20):
        self.calls.append(("list", limit))
        return [
            {
                "session_id": "sess-route",
                "status": "completed",
                "summary": "暂停当前低优先级任务",
                "updated_at": 1700000000.0,
            }
        ]
```

```python
    async def test_list_sessions_route_delegates_to_goal_runtime_service(self):
        fake_runtime = FakeGoalRuntimeService()
        fake_main = types.SimpleNamespace(
            app_state=types.SimpleNamespace(goal_runtime=fake_runtime)
        )

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            payload = await list_agent_runtime_sessions(limit=20)

        self.assertEqual(payload["sessions"][0]["session_id"], "sess-route")
        self.assertIn(("list", 20), fake_runtime.calls)
```

- [ ] **Step 2: Run the targeted tests and verify they fail**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_goal_runtime_data_store tests.test_goal_runtime_api -q
```

Expected: FAIL with missing `list_agent_sessions`, missing route import, or `AttributeError` on `goal_runtime.list_sessions`.

- [ ] **Step 3: Implement the minimal history query and API**

In `backend/app/services/goal_runtime/data_store_support.py`, add:

```python
async def list_agent_sessions(
    connection: aiosqlite.Connection,
    limit: int = 20,
) -> list[dict]:
    cursor = await connection.execute(
        """SELECT * FROM agent_runtime_sessions
           ORDER BY updated_at DESC
           LIMIT ?""",
        (max(1, int(limit)),),
    )
    rows = await cursor.fetchall()
    return [_normalize_session(row) for row in rows if row is not None]
```

Add this symbol to the existing import list in `backend/app/services/data_store.py`:

```python
list_agent_sessions as list_runtime_sessions,
```

```python
    async def list_agent_sessions(self, limit: int = 20) -> list[dict]:
        return await list_runtime_sessions(
            require_runtime_db(self._db),
            limit=limit,
        )
```

In `backend/app/services/goal_runtime/service.py`, add:

```python
    async def list_sessions(self, limit: int = 20) -> list[dict]:
        return await self.store.list_agent_sessions(limit=limit)
```

In `backend/app/api/agent_runtime.py`, add:

```python
from fastapi import APIRouter, HTTPException, Query
```

```python
@router.get("/sessions")
async def list_agent_runtime_sessions(limit: int = Query(default=20, ge=1, le=100)):
    from app.main import app_state

    return {"sessions": await app_state.goal_runtime.list_sessions(limit=limit)}
```

In `frontend/src/services/api.js`, add:

```javascript
export const getAgentRuntimeSessions = (limit = 20) =>
  api.get('/agent-runtime/sessions', { params: { limit } })
```

- [ ] **Step 4: Run the tests again and verify they pass**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_goal_runtime_data_store tests.test_goal_runtime_api -q
```

Expected: PASS, with latest session sorted first and `/api/agent-runtime/sessions` returning a `sessions` array.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/goal_runtime/data_store_support.py backend/app/services/data_store.py backend/app/services/goal_runtime/service.py backend/app/api/agent_runtime.py frontend/src/services/api.js tests/test_goal_runtime_data_store.py tests/test_goal_runtime_api.py
git commit -m "feat: add agent runtime session history api"
```

---

### Task 2: Create Unified Workbench Thread and Intent Helpers

**Files:**
- Create: `frontend/src/lib/agentSessionHistory.js`
- Create: `frontend/src/lib/agentSessionHistory.test.js`
- Create: `frontend/src/lib/agentWorkbenchThread.js`
- Create: `frontend/src/lib/agentWorkbenchThread.test.js`
- Create: `frontend/src/lib/agentWorkbenchIntent.js`
- Create: `frontend/src/lib/agentWorkbenchIntent.test.js`

- [ ] **Step 1: Write the failing helper tests**

Create `frontend/src/lib/agentSessionHistory.test.js`:

```javascript
import test from 'node:test'
import assert from 'node:assert/strict'

import { buildAgentSessionHistory } from './agentSessionHistory.js'

test('buildAgentSessionHistory keeps compact title status and timestamp only', () => {
  const items = buildAgentSessionHistory([
    {
      session_id: 'sess-1',
      status: 'awaiting_approval',
      summary: '把 GPU 0 的功耗上限调到 220W',
      updated_at: 1700000000,
    },
  ])

  assert.equal(items[0].id, 'sess-1')
  assert.equal(items[0].title, '把 GPU 0 的功耗上限调到 220W')
  assert.equal(items[0].status, 'awaiting_approval')
  assert.match(items[0].timeLabel, /\d{2}:\d{2}/)
})
```

Create `frontend/src/lib/agentWorkbenchThread.test.js`:

```javascript
import test from 'node:test'
import assert from 'node:assert/strict'

import { buildAgentWorkbenchThread } from './agentWorkbenchThread.js'

test('buildAgentWorkbenchThread maps runtime events into plan approval tool result and error cards', () => {
  const view = buildAgentWorkbenchThread({
    chatMessages: [
      { id: 'm1', role: 'user', content: '把 GPU 0 的功耗上限调到 220W' },
    ],
    runtimeSession: {
      status: 'awaiting_approval',
      awaiting_approval: true,
      pending_approval: { actions: [{ capability_name: 'scheduler.power_limit.set' }] },
    },
    runtimeEvents: [
      { event_type: 'PlanCreated', payload: { summary: '限制 GPU 0 功耗', steps: [] }, sequence: 1, timestamp: 1 },
      { event_type: 'AwaitingApproval', payload: { actions: [{ capability_name: 'scheduler.power_limit.set' }] }, sequence: 2, timestamp: 2 },
      { event_type: 'StepStarted', payload: { step_id: 'step-1', capability_name: 'runtime.snapshot.read' }, sequence: 3, timestamp: 3 },
      { event_type: 'SessionCompleted', payload: { summary: 'GPU 0 功耗已更新' }, sequence: 4, timestamp: 4 },
      { event_type: 'LLMCallFailed', payload: { error: '模型返回了非 JSON 内容' }, sequence: 5, timestamp: 5 },
    ],
  })

  assert.equal(view.topbar.statusLabel, '等待审批')
  assert.equal(view.topbar.approvalLabel, '待审批 1')
  assert.equal(view.items[0].kind, 'user_message')
  assert.equal(view.items[0].source, 'chat')
  assert.equal(view.items[1].kind, 'plan_card')
  assert.equal(view.items[2].kind, 'approval_card')
  assert.equal(view.items[3].kind, 'tool_event')
  assert.equal(view.items[3].collapsed, true)
  assert.equal(view.items[4].kind, 'result_card')
  assert.equal(view.items[5].kind, 'error_card')
  assert.equal(view.items[5].source, 'runtime')
})

test('buildAgentWorkbenchThread appends route confirm card for ambiguous inputs', () => {
  const view = buildAgentWorkbenchThread({
    chatMessages: [],
    runtimeSession: null,
    runtimeEvents: [],
    pendingRouteConfirm: {
      id: 'confirm-1',
      message: '帮我处理一下',
    },
  })

  assert.equal(view.items[0].kind, 'route_confirm_card')
  assert.equal(view.items[0].source, 'system')
})
```

Create `frontend/src/lib/agentWorkbenchIntent.test.js`:

```javascript
import test from 'node:test'
import assert from 'node:assert/strict'

import { resolveWorkbenchIntent } from './agentWorkbenchIntent.js'

test('resolveWorkbenchIntent routes clear runtime control requests to runtime', () => {
  assert.equal(resolveWorkbenchIntent('把 GPU 0 的功耗上限调到 220W').kind, 'runtime')
})

test('resolveWorkbenchIntent routes explanatory questions to chat', () => {
  assert.equal(resolveWorkbenchIntent('为什么当前有一张卡不可用？').kind, 'chat')
})

test('resolveWorkbenchIntent returns confirm for ambiguous inputs', () => {
  assert.equal(resolveWorkbenchIntent('帮我处理一下').kind, 'confirm')
})
```

- [ ] **Step 2: Run the helper tests and verify they fail**

Run:

```bash
node --test frontend/src/lib/agentSessionHistory.test.js frontend/src/lib/agentWorkbenchThread.test.js frontend/src/lib/agentWorkbenchIntent.test.js
```

Expected: FAIL with missing module exports.

- [ ] **Step 3: Implement the minimal helper modules**

Create `frontend/src/lib/agentSessionHistory.js`:

```javascript
function formatHistoryTime(value) {
  const ts = Number(value || 0)
  if (!ts) return '刚刚'
  return new Date(ts * 1000).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function buildAgentSessionHistory(sessions = []) {
  return sessions.map((session) => ({
    id: session.session_id,
    title: String(session.summary || session.goal_json?.message || '未命名会话').trim(),
    status: session.status || 'idle',
    timeLabel: formatHistoryTime(session.updated_at),
  }))
}
```

Create `frontend/src/lib/agentWorkbenchIntent.js`:

```javascript
const RUNTIME_PATTERNS = /(暂停|恢复|终止|调度|功耗上限|预算|priority|优先级|执行)/i
const CHAT_PATTERNS = /(为什么|怎么回事|解释|总结|分析|原因|风险)/i

export function resolveWorkbenchIntent(message = '') {
  const text = String(message || '').trim()
  if (!text) return { kind: 'empty' }
  if (RUNTIME_PATTERNS.test(text)) return { kind: 'runtime' }
  if (CHAT_PATTERNS.test(text)) return { kind: 'chat' }
  return { kind: 'confirm' }
}
```

Create `frontend/src/lib/agentWorkbenchThread.js`:

```javascript
const STATUS_LABELS = {
  idle: '未开始',
  running: '执行中',
  awaiting_approval: '等待审批',
  completed: '已完成',
  failed: '执行失败',
  aborted: '已终止',
}

function buildRuntimeItem(event) {
  if (event.event_type === 'PlanCreated') {
    return {
      id: `event-${event.sequence}`,
      kind: 'plan_card',
      source: 'runtime',
      summary: event.payload?.summary || '已生成执行计划',
      details: event.payload || {},
    }
  }
  if (event.event_type === 'AwaitingApproval') {
    return {
      id: `event-${event.sequence}`,
      kind: 'approval_card',
      source: 'runtime',
      summary: `待审批动作 ${event.payload?.actions?.length || 0} 条`,
      details: event.payload || {},
    }
  }
  if (event.event_type === 'SessionCompleted') {
    return {
      id: `event-${event.sequence}`,
      kind: 'result_card',
      source: 'runtime',
      summary: event.payload?.summary || '执行已完成',
      details: event.payload || {},
    }
  }
  if (event.event_type === 'SessionFailed' || event.event_type === 'LLMCallFailed') {
    return {
      id: `event-${event.sequence}`,
      kind: 'error_card',
      source: 'runtime',
      summary: event.payload?.error || event.payload?.summary || event.event_type,
      details: event.payload || {},
    }
  }
  return {
    id: `event-${event.sequence}`,
    kind: 'tool_event',
    source: 'runtime',
    summary: event.payload?.summary || event.event_type,
    collapsed: true,
    details: event.payload || {},
  }
}

function buildRouteConfirmItem(pendingRouteConfirm) {
  if (!pendingRouteConfirm) return []
  return [
    {
      id: pendingRouteConfirm.id,
      kind: 'route_confirm_card',
      source: 'system',
      message: pendingRouteConfirm.message,
    },
  ]
}

export function buildAgentWorkbenchThread({
  chatMessages = [],
  runtimeSession = null,
  runtimeEvents = [],
  pendingRouteConfirm = null,
}) {
  const pendingApprovalCount = runtimeSession?.pending_approval?.actions?.length || 0
  const items = [
    ...chatMessages.map((message, index) => ({
      id: message.id || `chat-${index}`,
      kind: message.role === 'user' ? 'user_message' : 'assistant_message',
      source: 'chat',
      role: message.role,
      content: message.content,
      suggestions: message.suggestions || [],
    })),
    ...runtimeEvents.map(buildRuntimeItem),
    ...buildRouteConfirmItem(pendingRouteConfirm),
  ]
  return {
    topbar: {
      modeLabel: '统一工作台',
      statusLabel: STATUS_LABELS[runtimeSession?.status] || '未开始',
      approvalLabel: runtimeSession?.awaiting_approval ? `待审批 ${pendingApprovalCount}` : '无需审批',
    },
    items,
  }
}
```

- [ ] **Step 4: Run the helper tests again and verify they pass**

Run:

```bash
node --test frontend/src/lib/agentSessionHistory.test.js frontend/src/lib/agentWorkbenchThread.test.js frontend/src/lib/agentWorkbenchIntent.test.js
```

Expected: PASS, with compact session history, deterministic intent routing, and unified thread items.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/agentSessionHistory.js frontend/src/lib/agentSessionHistory.test.js frontend/src/lib/agentWorkbenchThread.js frontend/src/lib/agentWorkbenchThread.test.js frontend/src/lib/agentWorkbenchIntent.js frontend/src/lib/agentWorkbenchIntent.test.js
git commit -m "feat: add ai workbench thread helpers"
```

---

### Task 3: Build the New Workbench Component Tree

**Files:**
- Create: `frontend/src/components/agent/AgentWorkbench.vue`
- Create: `frontend/src/components/agent/AgentSessionRail.vue`
- Create: `frontend/src/components/agent/AgentWorkbenchTopbar.vue`
- Create: `frontend/src/components/agent/AgentThread.vue`
- Create: `frontend/src/components/agent/AgentThreadItem.vue`
- Create: `frontend/src/components/agent/AgentThreadMessage.vue`
- Create: `frontend/src/components/agent/AgentThreadPlanCard.vue`
- Create: `frontend/src/components/agent/AgentThreadApprovalCard.vue`
- Create: `frontend/src/components/agent/AgentThreadToolEventCard.vue`
- Create: `frontend/src/components/agent/AgentThreadResultCard.vue`
- Create: `frontend/src/components/agent/AgentThreadErrorCard.vue`
- Create: `frontend/src/components/agent/AgentThreadRouteConfirmCard.vue`
- Create: `frontend/src/components/agent/AgentComposer.vue`
- Modify: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Write the failing structure tests**

Update `tests/test_frontend_ui_structure.py` with:

```python
    def test_ai_workbench_component_files_exist(self):
        for rel in [
            "frontend/src/components/agent/AgentWorkbench.vue",
            "frontend/src/components/agent/AgentSessionRail.vue",
            "frontend/src/components/agent/AgentWorkbenchTopbar.vue",
            "frontend/src/components/agent/AgentThread.vue",
            "frontend/src/components/agent/AgentThreadRouteConfirmCard.vue",
            "frontend/src/components/agent/AgentComposer.vue",
        ]:
            self.assertTrue((ROOT / rel).exists(), rel)
```

- [ ] **Step 2: Run the structure test and verify it fails**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure -q
```

Expected: FAIL because new component files do not exist and `AIAssistant.vue` still references old components.

- [ ] **Step 3: Create the minimal component skeletons**

Create `frontend/src/components/agent/AgentSessionRail.vue`:

```vue
<script setup>
const props = defineProps({
  sessions: { type: Array, default: () => [] },
  activeSessionId: { type: String, default: '' },
})

const emit = defineEmits(['select'])
</script>

<template>
  <aside class="agent-session-rail tech-card">
    <button
      v-for="session in sessions"
      :key="session.id"
      type="button"
      class="agent-session-rail__item"
      :class="{ 'agent-session-rail__item--active': session.id === activeSessionId }"
      @click="emit('select', session.id)"
    >
      <span class="agent-session-rail__status" :data-status="session.status"></span>
      <strong>{{ session.title }}</strong>
      <span>{{ session.timeLabel }}</span>
    </button>
  </aside>
</template>
```

Create `frontend/src/components/agent/AgentWorkbenchTopbar.vue`:

```vue
<script setup>
defineProps({
  model: { type: Object, required: true },
})
</script>

<template>
  <header class="agent-workbench-topbar tech-card">
    <span class="status-badge">{{ model.modeLabel }}</span>
    <span class="status-badge">{{ model.statusLabel }}</span>
    <span class="status-badge">{{ model.approvalLabel }}</span>
  </header>
</template>
```

Create `frontend/src/components/agent/AgentComposer.vue`:

```vue
<script setup>
defineProps({
  inputText: { type: String, required: true },
  quickPrompts: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:inputText', 'submit', 'usePrompt'])
</script>

<template>
  <footer class="agent-composer tech-card">
    <textarea
      :value="inputText"
      rows="4"
      @input="emit('update:inputText', $event.target.value)"
    />
    <div class="agent-composer__chips">
      <button
        v-for="item in quickPrompts"
        :key="item"
        type="button"
        class="btn-tech"
        @click="emit('usePrompt', item)"
      >
        {{ item }}
      </button>
    </div>
    <button type="button" class="btn-tech btn-tech--primary" :disabled="disabled" @click="emit('submit')">
      发送
    </button>
  </footer>
</template>
```

Create `frontend/src/components/agent/AgentThreadMessage.vue`:

```vue
<script setup>
import AgentChatMessageBody from './AgentChatMessageBody.vue'

defineProps({
  item: { type: Object, required: true },
})
</script>

<template>
  <article class="agent-thread-message" :data-role="item.role">
    <AgentChatMessageBody :message="{ role: item.role, content: item.content }" />
  </article>
</template>
```

Create `frontend/src/components/agent/AgentThread.vue` and `AgentThreadItem.vue`:

```vue
<!-- AgentThread.vue -->
<script setup>
import AgentThreadItem from './AgentThreadItem.vue'

defineProps({
  items: { type: Array, default: () => [] },
})

const emit = defineEmits(['approve', 'reject', 'chooseRoute'])
</script>

<template>
  <section class="agent-thread">
    <AgentThreadItem
      v-for="item in items"
      :key="item.id"
      :item="item"
      @approve="emit('approve', $event)"
      @reject="emit('reject', $event)"
      @choose-route="emit('chooseRoute', $event)"
    />
  </section>
</template>
```

```vue
<!-- AgentThreadItem.vue -->
<script setup>
import AgentThreadMessage from './AgentThreadMessage.vue'
import AgentThreadPlanCard from './AgentThreadPlanCard.vue'
import AgentThreadApprovalCard from './AgentThreadApprovalCard.vue'
import AgentThreadToolEventCard from './AgentThreadToolEventCard.vue'
import AgentThreadResultCard from './AgentThreadResultCard.vue'
import AgentThreadErrorCard from './AgentThreadErrorCard.vue'
import AgentThreadRouteConfirmCard from './AgentThreadRouteConfirmCard.vue'

defineProps({
  item: { type: Object, required: true },
})

const emit = defineEmits(['approve', 'reject', 'chooseRoute'])
</script>

<template>
  <AgentThreadMessage v-if="item.kind === 'user_message' || item.kind === 'assistant_message'" :item="item" />
  <AgentThreadPlanCard v-else-if="item.kind === 'plan_card'" :item="item" />
  <AgentThreadApprovalCard
    v-else-if="item.kind === 'approval_card'"
    :item="item"
    @approve="emit('approve', $event)"
    @reject="emit('reject', $event)"
  />
  <AgentThreadToolEventCard v-else-if="item.kind === 'tool_event'" :item="item" />
  <AgentThreadResultCard v-else-if="item.kind === 'result_card'" :item="item" />
  <AgentThreadErrorCard v-else-if="item.kind === 'error_card'" :item="item" />
  <AgentThreadRouteConfirmCard v-else :item="item" @choose="emit('chooseRoute', $event)" />
</template>
```

Create the card components with one responsibility each:

```vue
<!-- AgentThreadPlanCard.vue -->
<script setup>
defineProps({ item: { type: Object, required: true } })
</script>
<template><article class="tech-card"><strong>{{ item.summary }}</strong></article></template>
```

```vue
<!-- AgentThreadApprovalCard.vue -->
<script setup>
defineProps({ item: { type: Object, required: true } })
const emit = defineEmits(['approve', 'reject'])
</script>
<template>
  <article class="tech-card">
    <strong>{{ item.summary }}</strong>
    <div class="ink-inline-meta">
      <button class="btn-tech btn-tech--primary" @click="emit('approve', item)">批准</button>
      <button class="btn-tech" @click="emit('reject', item)">拒绝</button>
    </div>
  </article>
</template>
```

```vue
<!-- AgentThreadToolEventCard.vue -->
<script setup>
defineProps({ item: { type: Object, required: true } })
</script>
<template><article class="tech-card"><span>{{ item.summary }}</span></article></template>
```

```vue
<!-- AgentThreadResultCard.vue -->
<script setup>
defineProps({ item: { type: Object, required: true } })
</script>
<template><article class="tech-card"><strong>{{ item.summary }}</strong></article></template>
```

```vue
<!-- AgentThreadErrorCard.vue -->
<script setup>
defineProps({ item: { type: Object, required: true } })
</script>
<template><article class="tech-card"><strong>{{ item.summary }}</strong></article></template>
```

Create `frontend/src/components/agent/AgentThreadRouteConfirmCard.vue`:

```vue
<script setup>
defineProps({ item: { type: Object, required: true } })
const emit = defineEmits(['choose'])
</script>
<template>
  <article class="tech-card">
    <strong>这条输入还需要确认意图</strong>
    <p>{{ item.message }}</p>
    <div class="ink-inline-meta">
      <button class="btn-tech" @click="emit('choose', 'chat')">按解释处理</button>
      <button class="btn-tech btn-tech--primary" @click="emit('choose', 'runtime')">按执行处理</button>
    </div>
  </article>
</template>
```

Create `frontend/src/components/agent/AgentWorkbench.vue`:

```vue
<script setup>
import AgentComposer from './AgentComposer.vue'
import AgentSessionRail from './AgentSessionRail.vue'
import AgentThread from './AgentThread.vue'
import AgentWorkbenchTopbar from './AgentWorkbenchTopbar.vue'

defineProps({
  sessions: { type: Array, default: () => [] },
  activeSessionId: { type: String, default: '' },
  topbar: { type: Object, required: true },
  threadItems: { type: Array, default: () => [] },
  composerText: { type: String, required: true },
  quickPrompts: { type: Array, default: () => [] },
  busy: { type: Boolean, default: false },
})

const emit = defineEmits([
  'selectSession',
  'update:composerText',
  'submit',
  'usePrompt',
  'approve',
  'reject',
  'chooseRoute',
])
</script>

<template>
  <section class="agent-workbench">
    <AgentSessionRail
      :sessions="sessions"
      :active-session-id="activeSessionId"
      @select="emit('selectSession', $event)"
    />
    <div class="agent-workbench__main">
      <AgentWorkbenchTopbar :model="topbar" />
      <AgentThread
        :items="threadItems"
        @approve="emit('approve', $event)"
        @reject="emit('reject', $event)"
        @choose-route="emit('chooseRoute', $event)"
      />
      <AgentComposer
        :input-text="composerText"
        :quick-prompts="quickPrompts"
        :disabled="busy"
        @update:inputText="emit('update:composerText', $event)"
        @submit="emit('submit')"
        @usePrompt="emit('usePrompt', $event)"
      />
    </div>
  </section>
</template>
```

- [ ] **Step 4: Run the structure test again and verify it passes**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure -q
```

Expected: PASS for the new component existence assertions only; `AIAssistant.vue` 相关断言留到 Task 4 再切换。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/agent/AgentWorkbench.vue frontend/src/components/agent/AgentSessionRail.vue frontend/src/components/agent/AgentWorkbenchTopbar.vue frontend/src/components/agent/AgentThread.vue frontend/src/components/agent/AgentThreadItem.vue frontend/src/components/agent/AgentThreadMessage.vue frontend/src/components/agent/AgentThreadPlanCard.vue frontend/src/components/agent/AgentThreadApprovalCard.vue frontend/src/components/agent/AgentThreadToolEventCard.vue frontend/src/components/agent/AgentThreadResultCard.vue frontend/src/components/agent/AgentThreadErrorCard.vue frontend/src/components/agent/AgentThreadRouteConfirmCard.vue frontend/src/components/agent/AgentComposer.vue tests/test_frontend_ui_structure.py
git commit -m "feat: add ai unified workbench component tree"
```

---

### Task 4: Refactor AIAssistant.vue into Workbench + Model Tabs

**Files:**
- Modify: `frontend/src/views/AIAssistant.vue`
- Modify: `tests/test_frontend_ui_structure.py`
- Modify: `tests/test_real_data_only_structure.py`

- [ ] **Step 1: Write the failing AIAssistant structure assertions**

Update `tests/test_frontend_ui_structure.py`:

```python
    def test_ai_assistant_uses_workbench_and_model_tabs(self):
        text = (ROOT / "frontend/src/views/AIAssistant.vue").read_text(encoding="utf-8")

        self.assertIn("label: '工作台'", text)
        self.assertIn("label: '模型配置'", text)
        self.assertNotIn("label: '执行控制'", text)
        self.assertNotIn("label: '对话解释'", text)
        self.assertIn("AgentWorkbench", text)
        self.assertNotIn("AgentChatPane", text)
        self.assertNotIn("AgentControlDock", text)
        self.assertNotIn("AgentExecutionLedger", text)
```

Update `tests/test_real_data_only_structure.py`:

```python
    def test_ai_assistant_uses_unified_workbench_instead_of_ledger_page(self):
        ai_text = (ROOT / "frontend/src/views/AIAssistant.vue").read_text(encoding="utf-8")

        self.assertIn("AgentWorkbench", ai_text)
        self.assertNotIn("AgentExecutionLedger", ai_text)
        self.assertNotIn("AgentControlDock", ai_text)
```

- [ ] **Step 2: Run the structure tests and verify they fail**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure tests.test_real_data_only_structure -q
```

Expected: FAIL because `AIAssistant.vue` still uses `control/chat/model` tabs and old components.

- [ ] **Step 3: Rewrite the view orchestration around the new workbench**

Refactor `frontend/src/views/AIAssistant.vue` so tabs become:

```javascript
const assistantTabs = [
  { key: 'workbench', label: '工作台', desc: '统一对话与执行' },
  { key: 'model', label: '模型配置', desc: 'LLM 接入' },
]
const activeTab = ref('workbench')
```

Load session history:

```javascript
const sessionHistory = ref([])
const pendingRouteConfirm = ref(null)
const activeSessionId = computed(() => runtimeSession.value?.session_id || '')

async function loadSessionHistory() {
  const { data } = await getAgentRuntimeSessions(20)
  sessionHistory.value = buildAgentSessionHistory(data.sessions || [])
}
```

Build unified thread:

```javascript
const workbenchView = computed(() => buildAgentWorkbenchThread({
  chatMessages: messages.value,
  runtimeSession: runtimeSession.value,
  runtimeEvents: runtimeEvents.value,
  pendingRouteConfirm: pendingRouteConfirm.value,
}))
```

Route unified input:

```javascript
async function submitWorkbenchInput(message = controlInput.value.trim()) {
  const normalized = String(message || '').trim()
  if (!normalized) return
  const intent = resolveWorkbenchIntent(normalized)
  controlInput.value = normalized
  if (intent.kind === 'chat') {
    input.value = normalized
    pendingRouteConfirm.value = null
    await sendMessage()
    return
  }
  if (intent.kind === 'runtime') {
    pendingRouteConfirm.value = null
    await generateControlPlan(normalized)
    await loadSessionHistory()
    return
  }
  pendingRouteConfirm.value = {
    id: `route-${Date.now()}`,
    message: normalized,
  }
}

async function resolveRouteConfirm(kind) {
  const pending = pendingRouteConfirm.value
  if (!pending) return
  pendingRouteConfirm.value = null
  if (kind === 'chat') {
    input.value = pending.message
    controlInput.value = pending.message
    await sendMessage()
    return
  }
  await generateControlPlan(pending.message)
  await loadSessionHistory()
}

async function handleApproval(approved) {
  if (!runtimeSession.value?.session_id || controlExecuting.value) return
  controlExecuting.value = true
  try {
    await approveAgentRuntimeSession(runtimeSession.value.session_id, approved)
    await refreshRuntimeSession(runtimeSession.value.session_id)
    await loadSessionHistory()
  } finally {
    controlExecuting.value = false
  }
}
```

Extend the existing mounted bootstrap so session history loads with LLM config:

```javascript
onMounted(async () => {
  await loadAssistantCapability()
  await loadSessionHistory()
})
```

Render the new workbench:

```vue
<AgentWorkbench
  v-if="activeTab === 'workbench'"
  :sessions="sessionHistory"
  :active-session-id="activeSessionId"
  :topbar="workbenchView.topbar"
  :thread-items="workbenchView.items"
  :composer-text="controlInput"
  :quick-prompts="QUICK_CONTROLS"
  :busy="loading || controlPlanning || controlExecuting"
  @select-session="refreshRuntimeSession"
  @update:composerText="controlInput = $event"
  @submit="submitWorkbenchInput"
  @use-prompt="useControlPrompt"
  @approve="handleApproval(true)"
  @reject="handleApproval(false)"
  @choose-route="resolveRouteConfirm"
/>
<AgentModelConfigPane
  v-else
  :llm-ready="llmReady"
  :llm-busy="llmBusy"
  :llm-notice="llmNotice"
  :llm-feedback="llmFeedback"
  :llm-form="llmForm"
  :has-stored-key="hasStoredKey"
  :saved-key-hint="savedKeyHint"
  :llm-source-label="llmSourceLabel"
  :llm-updated-at="llmUpdatedAt"
  :can-test-llm="canTestLlm"
  :can-save-llm="canSaveLlm"
  @run-test="runLlmTest"
  @save="saveLlmConfig"
/>
```

Remove these imports and usage sites:

```javascript
import AgentControlDock from '../components/agent/AgentControlDock.vue'
import AgentExecutionLedger from '../components/agent/AgentExecutionLedger.vue'
import AgentChatPane from '../components/agent/AgentChatPane.vue'
import PlannerLivePanel from '../components/agent/PlannerLivePanel.vue'
```

- [ ] **Step 4: Run the structure tests again and verify they pass**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure tests.test_real_data_only_structure -q
```

Expected: PASS with `工作台 + 模型配置` tabs, unified workbench, and no legacy execution ledger page.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/AIAssistant.vue frontend/src/services/api.js tests/test_frontend_ui_structure.py tests/test_real_data_only_structure.py
git commit -m "feat: unify ai assistant into chat workbench"
```

---

### Task 5: Remove Legacy Execution-Ledger Components and Verify End-to-End

**Files:**
- Delete: `frontend/src/components/agent/AgentControlDock.vue`
- Delete: `frontend/src/components/agent/AgentControlSessionCard.vue`
- Delete: `frontend/src/components/agent/AgentExecutionLedger.vue`
- Delete: `frontend/src/components/agent/AgentRunOverviewBar.vue`
- Delete: `frontend/src/components/agent/PlannerLivePanel.vue`
- Modify: `tests/test_frontend_ui_structure.py`
- Modify: `tests/test_real_data_only_structure.py`

- [ ] **Step 1: Write the failing cleanup assertions**

Add to `tests/test_frontend_ui_structure.py`:

```python
    def test_ai_assistant_legacy_execution_ledger_components_are_removed(self):
        for rel in [
            "frontend/src/components/agent/AgentControlDock.vue",
            "frontend/src/components/agent/AgentControlSessionCard.vue",
            "frontend/src/components/agent/AgentExecutionLedger.vue",
            "frontend/src/components/agent/AgentRunOverviewBar.vue",
            "frontend/src/components/agent/PlannerLivePanel.vue",
        ]:
            self.assertFalse((ROOT / rel).exists(), rel)
```

- [ ] **Step 2: Run the cleanup test and verify it fails**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure -q
```

Expected: FAIL because the legacy files still exist.

- [ ] **Step 3: Delete the legacy files and remove stale references**

Delete:

```text
frontend/src/components/agent/AgentControlDock.vue
frontend/src/components/agent/AgentControlSessionCard.vue
frontend/src/components/agent/AgentExecutionLedger.vue
frontend/src/components/agent/AgentRunOverviewBar.vue
frontend/src/components/agent/PlannerLivePanel.vue
```

Also remove any remaining imports or strings in `tests/test_frontend_ui_structure.py` and `tests/test_real_data_only_structure.py` that assert the old ledger page is primary.

- [ ] **Step 4: Run focused and final verification**

Run:

```bash
node --test frontend/src/lib/agentSessionHistory.test.js frontend/src/lib/agentWorkbenchThread.test.js frontend/src/lib/agentWorkbenchIntent.test.js
```

Expected: PASS

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_goal_runtime_data_store tests.test_goal_runtime_api tests.test_frontend_ui_structure tests.test_real_data_only_structure -q
```

Expected: PASS

Run:

```bash
npm --prefix frontend run build
```

Expected: production build succeeds without references to removed components.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/agent frontend/src/views/AIAssistant.vue tests/test_frontend_ui_structure.py tests/test_real_data_only_structure.py
git commit -m "refactor: remove legacy ai execution ledger layout"
```

---

## Self-Review

### Spec coverage

- `执行控制` 与 `对话解释` 合并：Task 4
- 左侧紧凑会话栏：Task 1, Task 2, Task 3
- 顶部薄状态条：Task 2, Task 3
- 聊天流内计划 / 审批 / 工具调用 / 结果 / 错误卡：Task 2, Task 3
- 模糊输入确认卡：Task 2, Task 3, Task 4
- 审批通过 / 拒绝在线程内回显：Task 3, Task 4
- 工具调用卡默认折叠：Task 2
- 删除旧控制台 / 账本双栏：Task 4, Task 5
- 保留模型配置独立子页：Task 4

### Placeholder scan

- 未使用 `TODO`、`TBD`、`similar to`
- 每个代码步骤都包含实际代码块
- 每个验证步骤都包含精确命令与预期

### Type consistency

- Session history helper统一输出 `id / title / status / timeLabel`
- 线程 helper 统一输出 `topbar / items`
- 线程项统一携带 `source: chat | runtime | system`
- 新视图统一使用 `AgentWorkbench`
- 模糊输入统一返回 `confirm`
