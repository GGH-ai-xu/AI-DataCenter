# AI 助手统一入口 LLM 判路 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除 AI 助手前端“按解释处理 / 按执行处理”的本地判路与二次确认，改为统一输入框先调用后端 LLM 判路接口，再决定进入聊天流或 runtime 执行链。

**Architecture:** 后端在 `backend/app/api/ai.py` 增加一个新的 `dispatch` 接口，并在 `backend/app/services/llm.py` 增加结构化判路方法，结合现有 GPU / 进程上下文输出稳定 JSON。前端删除 `agentWorkbenchIntent.js` 和 route confirm 卡片链，统一由 `useAiAssistantWorkbench.js` 先调用新的 dispatch API，再进入现有 `/api/ai/chat/stream` 或 `/api/agent-runtime/sessions`。

**Tech Stack:** FastAPI, Pydantic, Python `unittest`, Vue 3 composables, Node `node:test`, Axios, SSE

---

## File Structure

- Create: `tests/test_ai_workbench_dispatch_api.py`
  - 覆盖后端统一判路接口的 chat / runtime / invalid-response / llm-unavailable 场景。
- Modify: `backend/app/models/schemas.py`
  - 新增 AI 工作台判路请求与响应 schema。
- Modify: `backend/app/services/llm.py`
  - 新增 `dispatch_workbench_message()` 和对应的结构化提示词、校验逻辑。
- Modify: `backend/app/api/ai.py`
  - 新增 `POST /api/ai/workbench/dispatch` 并接线到 LLM 判路方法。
- Delete: `frontend/src/lib/agentWorkbenchIntent.js`
  - 删除前端关键词判路器。
- Delete: `frontend/src/lib/agentWorkbenchIntent.test.js`
  - 删除前端关键词判路测试。
- Create: `frontend/src/lib/agentWorkbenchDispatch.js`
  - 将后端 dispatch 响应规范化成前端可执行动作，保持纯函数可测试。
- Create: `frontend/src/lib/agentWorkbenchDispatch.test.js`
  - 覆盖 `chat_inline / chat_stream / runtime / invalid` 四类判路结果。
- Modify: `frontend/src/services/api.js`
  - 新增 `dispatchAiWorkbenchMessage()` API 封装。
- Modify: `frontend/src/composables/useAiAssistantWorkbench.js`
  - 删除 `pendingRouteConfirm` 和 `resolveRouteConfirm`，改为统一 dispatch 提交流程。
- Modify: `frontend/src/lib/agentWorkbenchThread.js`
  - 删除 `pendingRouteConfirm` 参数与 route confirm 卡片生成逻辑。
- Modify: `frontend/src/lib/agentWorkbenchThread.test.js`
  - 删除 route confirm 断言，保留普通 chat/runtime 事件映射断言。
- Modify: `frontend/src/components/agent/AgentThread.vue`
  - 删除 `choose-route` emit 链。
- Modify: `frontend/src/components/agent/AgentThreadItem.vue`
  - 删除 route confirm 卡片分支和 `chooseRoute` emit。
- Modify: `frontend/src/components/agent/AgentWorkbench.vue`
  - 删除 `chooseRoute` emit 链。
- Modify: `frontend/src/views/AIAssistant.vue`
  - 删除 `@choose-route="resolveRouteConfirm"` 绑定。
- Delete: `frontend/src/components/agent/AgentThreadRouteConfirmCard.vue`
  - 删除旧的“按解释处理 / 按执行处理”卡片组件。
- Modify: `tests/test_frontend_ui_structure.py`
  - 新增“已删除本地 intent 判路和 route confirm 链”的结构断言。

## Task 1: Lock The Backend Dispatch Contract With Failing Tests

**Files:**
- Create: `tests/test_ai_workbench_dispatch_api.py`
- Modify: `backend/app/models/schemas.py`

- [ ] **Step 1: Write the failing API tests for the new dispatch route**

Create `tests/test_ai_workbench_dispatch_api.py` with these tests:

```python
import os
import sys
import types
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from fastapi import HTTPException  # noqa: E402
from app.api.ai import dispatch_workbench_message  # noqa: E402
from app.models.schemas import AiWorkbenchDispatchRequest  # noqa: E402


class FakeAgent:
    async def get_all_gpus(self):
        return []

    async def get_system_info(self):
        return {}

    async def get_processes(self):
        return []


class FakeImportContext:
    def filter_gpus(self, gpus):
        return gpus

    def filter_processes(self, processes):
        return processes


class FakePrivacy:
    def sanitize_processes(self, processes):
        return processes


class FakeLLM:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    async def dispatch_workbench_message(self, message, gpu_context=""):
        self.calls.append((message, gpu_context))
        if self.error:
            raise self.error
        return dict(self.result)


class AIWorkbenchDispatchRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_dispatch_returns_chat_stream_result(self):
        fake_llm = FakeLLM({"route_kind": "chat", "reply_mode": "stream"})
        fake_state = types.SimpleNamespace(
            llm=fake_llm,
            agent=FakeAgent(),
            import_context=FakeImportContext(),
            privacy=FakePrivacy(),
        )
        fake_main = types.SimpleNamespace(app_state=fake_state)

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            result = await dispatch_workbench_message(
                AiWorkbenchDispatchRequest(message="为什么 GPU 0 不可用？")
            )

        self.assertEqual(result["route_kind"], "chat")
        self.assertEqual(result["reply_mode"], "stream")
        self.assertEqual(fake_llm.calls[0][0], "为什么 GPU 0 不可用？")

    async def test_dispatch_returns_runtime_result(self):
        fake_llm = FakeLLM(
            {"route_kind": "runtime", "message": "把 GPU 0 功耗限制到 220W"}
        )
        fake_state = types.SimpleNamespace(
            llm=fake_llm,
            agent=FakeAgent(),
            import_context=FakeImportContext(),
            privacy=FakePrivacy(),
        )
        fake_main = types.SimpleNamespace(app_state=fake_state)

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            result = await dispatch_workbench_message(
                AiWorkbenchDispatchRequest(message="把 GPU 0 功耗限制到 220W")
            )

        self.assertEqual(result["route_kind"], "runtime")
        self.assertEqual(result["message"], "把 GPU 0 功耗限制到 220W")

    async def test_dispatch_raises_503_when_llm_missing(self):
        fake_state = types.SimpleNamespace(
            llm=None,
            agent=FakeAgent(),
            import_context=FakeImportContext(),
            privacy=FakePrivacy(),
        )
        fake_main = types.SimpleNamespace(app_state=fake_state)

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            with self.assertRaises(HTTPException) as ctx:
                await dispatch_workbench_message(
                    AiWorkbenchDispatchRequest(message="帮我处理一下")
                )

        self.assertEqual(ctx.exception.status_code, 503)

    async def test_dispatch_raises_502_when_llm_returns_invalid_result(self):
        fake_llm = FakeLLM(error=ValueError("AI 工作台判路结果不是合法 JSON"))
        fake_state = types.SimpleNamespace(
            llm=fake_llm,
            agent=FakeAgent(),
            import_context=FakeImportContext(),
            privacy=FakePrivacy(),
        )
        fake_main = types.SimpleNamespace(app_state=fake_state)

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            with self.assertRaises(HTTPException) as ctx:
                await dispatch_workbench_message(
                    AiWorkbenchDispatchRequest(message="帮我处理一下")
                )

        self.assertEqual(ctx.exception.status_code, 502)
```

- [ ] **Step 2: Run the new backend test to verify it fails**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_ai_workbench_dispatch_api -q
```

Expected: FAIL because `AiWorkbenchDispatchRequest` and `dispatch_workbench_message` do not exist yet.

- [ ] **Step 3: Add the new dispatch schemas**

In `backend/app/models/schemas.py`, add these models below `ChatResponse`:

```python
class AiWorkbenchDispatchRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class AiWorkbenchDispatchResponse(BaseModel):
    route_kind: str = Field(pattern=r"^(chat|runtime)$")
    reply_mode: Optional[str] = Field(default=None, pattern=r"^(inline|stream)$")
    reply: str = ""
    message: str = ""
```

- [ ] **Step 4: Run the backend test again and verify it still fails on the missing route**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_ai_workbench_dispatch_api -q
```

Expected: FAIL because `backend/app/api/ai.py` still has no `dispatch_workbench_message` route function.

## Task 2: Implement The Backend LLM Dispatch Route

**Files:**
- Modify: `backend/app/services/llm.py`
- Modify: `backend/app/api/ai.py`
- Create: `tests/test_ai_workbench_dispatch_api.py`

- [ ] **Step 1: Add the structured LLM dispatch prompt and parser**

In `backend/app/services/llm.py`, add this prompt near `CONTROL_PROMPT`:

```python
WORKBENCH_DISPATCH_PROMPT = """你是 AI 助手统一工作台的判路器。

你的任务是判断用户当前这句话应该进入：
1. chat
2. runtime

约束：
- 只能输出 JSON
- route_kind 只能是 chat 或 runtime
- 如果信息不足，返回 chat，并用 reply_mode=inline 给出追问
- 如果是明确问答，返回 chat，并用 reply_mode=stream
- 如果是明确执行请求且信息足够，返回 runtime
- 不允许输出第三种模式

返回格式：
{
  "route_kind": "chat|runtime",
  "reply_mode": "inline|stream",
  "reply": "仅 chat+inline 时填写",
  "message": "仅 runtime 时填写"
}"""
```

Then add this method inside `LLMService`:

```python
    async def dispatch_workbench_message(self, user_message: str, gpu_context: str = "") -> dict:
        messages = [{"role": "system", "content": WORKBENCH_DISPATCH_PROMPT}]
        if gpu_context:
            messages.append({
                "role": "system",
                "content": f"当前GPU集群实时状态：\n{gpu_context}",
            })
        messages.append({"role": "user", "content": user_message})

        content = await self._call_with_retry(
            model=self.model,
            messages=messages,
            temperature=0.1,
        )
        parsed = self.parse_structured_json(content, label="AI 工作台判路结果")
        route_kind = str(parsed.get("route_kind") or "").strip()
        reply_mode = str(parsed.get("reply_mode") or "").strip()
        reply = str(parsed.get("reply") or "").strip()
        message = str(parsed.get("message") or user_message).strip()

        if route_kind not in {"chat", "runtime"}:
            raise ValueError("AI 工作台判路结果缺少合法的 route_kind")
        if route_kind == "chat" and reply_mode not in {"inline", "stream"}:
            raise ValueError("AI 工作台判路结果缺少合法的 reply_mode")
        if route_kind == "chat" and reply_mode == "inline" and not reply:
            raise ValueError("AI 工作台判路结果缺少 inline reply")
        if route_kind == "runtime" and not message:
            raise ValueError("AI 工作台判路结果缺少 runtime message")

        return {
            "route_kind": route_kind,
            "reply_mode": reply_mode or None,
            "reply": reply,
            "message": message if route_kind == "runtime" else "",
        }
```

- [ ] **Step 2: Run the backend test and verify it still fails on the missing API route**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_ai_workbench_dispatch_api -q
```

Expected: FAIL because `backend/app/api/ai.py` still exports no `dispatch_workbench_message`.

- [ ] **Step 3: Add the new API route in `backend/app/api/ai.py`**

Update the schema import:

```python
from app.models.schemas import (
    AiWorkbenchDispatchRequest,
    ChatRequest,
)
```

Add this route above `@router.post("/chat")`:

```python
@router.post("/workbench/dispatch")
async def dispatch_workbench_message(req: AiWorkbenchDispatchRequest):
    from app.main import app_state

    llm = _require_llm(app_state)
    gpu_context = await _build_gpu_context(app_state)
    try:
        return await llm.dispatch_workbench_message(req.message, gpu_context)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
```

- [ ] **Step 4: Run the backend dispatch tests and verify they pass**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_ai_workbench_dispatch_api -q
```

Expected: PASS with four green cases for chat stream, runtime, 503, and 502 handling.

- [ ] **Step 5: Commit the backend dispatch contract and route**

Run:

```bash
git add backend/app/models/schemas.py backend/app/services/llm.py backend/app/api/ai.py tests/test_ai_workbench_dispatch_api.py
git commit -m "feat: add ai workbench dispatch api"
```

Expected: commit succeeds with only the backend dispatch files staged.

## Task 3: Lock The Frontend Against Local Intent Routing

**Files:**
- Modify: `tests/test_frontend_ui_structure.py`
- Delete: `frontend/src/lib/agentWorkbenchIntent.test.js`
- Modify: `frontend/src/lib/agentWorkbenchThread.test.js`
- Create: `frontend/src/lib/agentWorkbenchDispatch.test.js`

- [ ] **Step 1: Add failing structure assertions that the old intent classifier is gone**

In `tests/test_frontend_ui_structure.py`, add:

```python
    def test_ai_assistant_uses_backend_dispatch_instead_of_local_intent_rules(self):
        workbench_text = (
            ROOT / "frontend/src/composables/useAiAssistantWorkbench.js"
        ).read_text(encoding="utf-8")
        view_text = (ROOT / "frontend/src/views/AIAssistant.vue").read_text(encoding="utf-8")

        self.assertIn("dispatchAiWorkbenchMessage", workbench_text)
        self.assertNotIn("resolveWorkbenchIntent", workbench_text)
        self.assertNotIn("pendingRouteConfirm", workbench_text)
        self.assertNotIn("resolveRouteConfirm", workbench_text)
        self.assertNotIn("@choose-route", view_text)

    def test_ai_workbench_thread_no_longer_builds_route_confirm_cards(self):
        thread_text = (
            ROOT / "frontend/src/lib/agentWorkbenchThread.js"
        ).read_text(encoding="utf-8")

        self.assertNotIn("route_confirm_card", thread_text)
        self.assertNotIn("pendingRouteConfirm", thread_text)
```

- [ ] **Step 2: Replace the old intent test with dispatch-result tests**

Create `frontend/src/lib/agentWorkbenchDispatch.test.js`:

```javascript
import test from 'node:test'
import assert from 'node:assert/strict'

import { resolveWorkbenchDispatchResult } from './agentWorkbenchDispatch.js'

test('resolveWorkbenchDispatchResult maps chat inline reply', () => {
  assert.deepEqual(
    resolveWorkbenchDispatchResult({
      route_kind: 'chat',
      reply_mode: 'inline',
      reply: '请先说明你要解释还是执行。',
    }),
    { kind: 'chat_inline', reply: '请先说明你要解释还是执行。' },
  )
})

test('resolveWorkbenchDispatchResult maps chat stream reply', () => {
  assert.deepEqual(
    resolveWorkbenchDispatchResult({
      route_kind: 'chat',
      reply_mode: 'stream',
    }),
    { kind: 'chat_stream' },
  )
})

test('resolveWorkbenchDispatchResult maps runtime reply', () => {
  assert.deepEqual(
    resolveWorkbenchDispatchResult({
      route_kind: 'runtime',
      message: '把 GPU 0 功耗限制到 220W',
    }),
    { kind: 'runtime', message: '把 GPU 0 功耗限制到 220W' },
  )
})

test('resolveWorkbenchDispatchResult rejects invalid payload', () => {
  assert.throws(
    () => resolveWorkbenchDispatchResult({ route_kind: 'chat' }),
    /AI 工作台判路结果无效/,
  )
})
```

Delete `frontend/src/lib/agentWorkbenchIntent.test.js` from the repo.

- [ ] **Step 3: Remove the route confirm test from `agentWorkbenchThread.test.js`**

Delete the second test block:

```javascript
test('buildAgentWorkbenchThread appends route confirm card for ambiguous inputs', () => {
  ...
})
```

- [ ] **Step 4: Run the targeted frontend tests and verify they fail**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure.FrontendUIStructureTests.test_ai_assistant_uses_backend_dispatch_instead_of_local_intent_rules tests.test_frontend_ui_structure.FrontendUIStructureTests.test_ai_workbench_thread_no_longer_builds_route_confirm_cards
node --test frontend/src/lib/agentWorkbenchDispatch.test.js frontend/src/lib/agentWorkbenchThread.test.js
```

Expected:
- Python structure tests FAIL because the old local intent routing still exists
- Node test FAIL because `agentWorkbenchDispatch.js` does not exist yet

## Task 4: Refactor The Frontend Workbench To Use Backend Dispatch

**Files:**
- Create: `frontend/src/lib/agentWorkbenchDispatch.js`
- Modify: `frontend/src/services/api.js`
- Modify: `frontend/src/composables/useAiAssistantWorkbench.js`
- Modify: `frontend/src/lib/agentWorkbenchThread.js`
- Modify: `frontend/src/components/agent/AgentThread.vue`
- Modify: `frontend/src/components/agent/AgentThreadItem.vue`
- Modify: `frontend/src/components/agent/AgentWorkbench.vue`
- Modify: `frontend/src/views/AIAssistant.vue`
- Delete: `frontend/src/components/agent/AgentThreadRouteConfirmCard.vue`
- Delete: `frontend/src/lib/agentWorkbenchIntent.js`
- Delete: `frontend/src/lib/agentWorkbenchIntent.test.js`

- [ ] **Step 1: Add the frontend dispatch-response helper**

Create `frontend/src/lib/agentWorkbenchDispatch.js`:

```javascript
export function resolveWorkbenchDispatchResult(payload = {}) {
  const routeKind = String(payload?.route_kind || '').trim()
  const replyMode = String(payload?.reply_mode || '').trim()
  const reply = String(payload?.reply || '').trim()
  const message = String(payload?.message || '').trim()

  if (routeKind === 'chat' && replyMode === 'inline' && reply) {
    return { kind: 'chat_inline', reply }
  }
  if (routeKind === 'chat' && replyMode === 'stream') {
    return { kind: 'chat_stream' }
  }
  if (routeKind === 'runtime' && message) {
    return { kind: 'runtime', message }
  }
  throw new Error('AI 工作台判路结果无效。')
}
```

- [ ] **Step 2: Add the dispatch API wrapper**

In `frontend/src/services/api.js`, add:

```javascript
export const dispatchAiWorkbenchMessage = (message) =>
  api.post('/ai/workbench/dispatch', { message })
```

Place it above `openAiChatStream`.

- [ ] **Step 3: Rewrite `useAiAssistantWorkbench.js` around a single dispatch-first flow**

Make these import changes:

```javascript
import { resolveWorkbenchDispatchResult } from '../lib/agentWorkbenchDispatch.js'
import { dispatchAiWorkbenchMessage, openAiChatStream } from '../services/api'
```

Remove:

```javascript
import { resolveWorkbenchIntent } from '../lib/agentWorkbenchIntent.js'
```

Delete:

```javascript
const pendingRouteConfirm = ref(null)
```

Refactor the internal flow into these helpers:

```javascript
  function appendUserMessage(text) {
    messages.value.push({ id: nextMessageId('user'), role: 'user', content: text })
  }

  async function streamChatReply(text) {
    const assistantIndex = messages.value.length
    messages.value.push(buildPendingAssistantMessage(nextMessageId('assistant')))
    let chatState = { text: '', suggestions: [], error: '' }
    const response = await openAiChatStream(text)
    for await (const frame of parseSseFrames(readResponseTextChunks(response))) {
      chatState = reduceChatStreamEvent(chatState, frame)
      replaceAssistantMessage(assistantIndex, chatState)
    }
  }

  async function runRuntimeFromSubmittedMessage(text) {
    await runtime.startRuntimeRequest(text)
  }
```

Replace `submitWorkbenchInput` with:

```javascript
  async function submitWorkbenchInput(message = composerText.value.trim()) {
    const text = String(message || '').trim()
    if (!text || loading.value || controlPlanning.value || controlExecuting.value) return

    appendUserMessage(text)
    composerText.value = ''
    loading.value = true

    try {
      const { data } = await dispatchAiWorkbenchMessage(text)
      const action = resolveWorkbenchDispatchResult(data)
      if (action.kind === 'chat_inline') {
        pushAssistantMessage(action.reply)
        return
      }
      if (action.kind === 'chat_stream') {
        await streamChatReply(text)
        return
      }
      await runRuntimeFromSubmittedMessage(action.message)
    } catch (error) {
      pushAssistantMessage(
        error?.response?.data?.detail
          || error?.message
          || 'AI 判路失败，请检查模型配置。'
      )
    } finally {
      loading.value = false
    }
  }
```

Delete the exported `resolveRouteConfirm` and stop returning it.

- [ ] **Step 4: Remove route confirm cards and emit chains**

In `frontend/src/lib/agentWorkbenchThread.js`, delete `buildRouteConfirmItems()` and remove `pendingRouteConfirm` from the exported function signature:

```javascript
export function buildAgentWorkbenchThread({
  chatMessages = [],
  runtimeEvents = [],
}) {
  return {
    topbar: {},
    items: [
      ...chatMessages.map(buildMessageItem),
      ...runtimeEvents.map(buildRuntimeItem),
    ],
  }
}
```

In `frontend/src/components/agent/AgentThread.vue`, change:

```vue
const emit = defineEmits(['approve', 'reject', 'chooseRoute'])
```

to:

```vue
const emit = defineEmits(['approve', 'reject'])
```

and delete the `@choose-route` forwarding.

In `frontend/src/components/agent/AgentThreadItem.vue`, delete:

```vue
import AgentThreadRouteConfirmCard from './AgentThreadRouteConfirmCard.vue'
```

Change:

```vue
const emit = defineEmits(['approve', 'reject', 'chooseRoute'])
```

to:

```vue
const emit = defineEmits(['approve', 'reject'])
```

Then remove the trailing `AgentThreadRouteConfirmCard` branch so `error_card` becomes the final rendered variant.

In `frontend/src/components/agent/AgentWorkbench.vue`, remove `chooseRoute` from `defineEmits()` and delete the `@choose-route` binding passed into `AgentThread`.

In `frontend/src/views/AIAssistant.vue`, delete:

```vue
@choose-route="resolveRouteConfirm"
```

- [ ] **Step 5: Delete the old local intent module**

Delete:

```text
frontend/src/components/agent/AgentThreadRouteConfirmCard.vue
frontend/src/lib/agentWorkbenchIntent.js
frontend/src/lib/agentWorkbenchIntent.test.js
```

- [ ] **Step 6: Run the targeted frontend tests and verify they pass**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure.FrontendUIStructureTests.test_ai_assistant_uses_backend_dispatch_instead_of_local_intent_rules tests.test_frontend_ui_structure.FrontendUIStructureTests.test_ai_workbench_thread_no_longer_builds_route_confirm_cards
node --test frontend/src/lib/agentWorkbenchDispatch.test.js frontend/src/lib/agentWorkbenchThread.test.js
```

Expected: PASS with no references to local intent routing or route confirm cards.

- [ ] **Step 7: Commit the frontend dispatch refactor**

Run:

```bash
git add frontend/src/services/api.js frontend/src/composables/useAiAssistantWorkbench.js frontend/src/lib/agentWorkbenchDispatch.js frontend/src/lib/agentWorkbenchDispatch.test.js frontend/src/lib/agentWorkbenchThread.js frontend/src/lib/agentWorkbenchThread.test.js frontend/src/components/agent/AgentThread.vue frontend/src/components/agent/AgentThreadItem.vue frontend/src/components/agent/AgentWorkbench.vue frontend/src/views/AIAssistant.vue tests/test_frontend_ui_structure.py
git rm frontend/src/components/agent/AgentThreadRouteConfirmCard.vue frontend/src/lib/agentWorkbenchIntent.js frontend/src/lib/agentWorkbenchIntent.test.js
git commit -m "refactor: route ai assistant through backend dispatch"
```

Expected: commit succeeds with only the dispatch-related frontend files staged.

## Task 5: Full Verification

**Files:**
- Modify: none

- [ ] **Step 1: Run repository tests covering the new dispatch path**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_ai_workbench_dispatch_api tests.test_ai_chat_stream_api tests.test_frontend_ui_structure tests.test_real_data_only_structure -q
node --test frontend/src/lib/agentWorkbenchDispatch.test.js frontend/src/lib/agentWorkbenchThread.test.js
```

Expected:
- Python tests PASS
- Node tests PASS

- [ ] **Step 2: Run the production frontend build**

Run:

```bash
npm --prefix frontend run build
```

Expected: PASS with the normal rolldown/vite bundle output and no dispatch-related build errors.

- [ ] **Step 3: Smoke-check the new user-visible behavior manually**

Run the app and verify:

1. 输入“为什么 GPU 0 不可用？”时，不再出现“按解释处理 / 按执行处理”，而是直接进入聊天回答。
2. 输入“帮我处理一下”时，不再出现二选一卡片，而是在聊天线程里收到一条追问。
3. 输入“把 GPU 0 功耗限制到 220W”时，不再出现二选一卡片，而是直接创建 runtime session，并保留原有审批链。

- [ ] **Step 4: Commit final verification-only changes if needed**

Run:

```bash
git status --short
```

Expected: no unexpected files remain modified beyond the planned dispatch changes.
