# AI 助手与 Goal Runtime 流式输出 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 AI 问答助手和 goal runtime 执行控制台增加真实流式输出，让问答消息和执行账本都能在模型生成过程中实时更新，同时只持久化最新快照和最终完整结果。

**Architecture:** 后端先给 `LLMService` 增加真实 stream 能力，并在 API 层统一用 `text/event-stream` 帧输出；goal runtime 进一步拆成“先建 session，再后台运行，再通过 per-session stream 持续推送 planner 文本和 runtime 事件”。前端放弃原生 `EventSource`，改用带 `Authorization` header 的 `fetch + ReadableStream` 解析 SSE 帧，再把问答消息、planner live panel 和 execution ledger 接到同一套流式状态机上。

**Tech Stack:** FastAPI, Python, SQLite, Vue 3, Fetch Streams, node:test, Vite, repository-level Python tests

---

## File Structure

### Backend

- Modify: `backend/app/services/llm.py`
  Purpose: 为 chat 与 control plan 增加真实流式调用、能力探测和增量文本提取。
- Create: `backend/app/services/sse.py`
  Purpose: 统一编码 `text/event-stream` 帧，避免 `ai.py` 与 `agent_runtime.py` 各自手拼字符串。
- Modify: `backend/app/services/goal_runtime/data_store_support.py`
  Purpose: 增加 `live_phase` 和 `agent_runtime_stream_state` 持久化。
- Modify: `backend/app/services/data_store.py`
  Purpose: 暴露 runtime stream state 的覆盖式读写包装。
- Create: `backend/app/services/goal_runtime/session_stream.py`
  Purpose: 提供 per-session 内存订阅/发布 broker，支持多个前端订阅同一 session。
- Modify: `backend/app/services/goal_runtime/session_view.py`
  Purpose: 把 `live_phase` 与 `planner_stream` 合并进 session view。
- Modify: `backend/app/services/goal_runtime/reasoning_trace.py`
  Purpose: 支持流式 planner 文本聚合、节流快照回调和最终 structured plan 提取。
- Modify: `backend/app/services/goal_runtime/service.py`
  Purpose: 改成“先创建 session、后台启动、持续推流”，并暴露 session stream 订阅接口。
- Modify: `backend/app/api/agent_runtime.py`
  Purpose: 新增 `/sessions/{id}/stream`，并让创建 session 立即返回 `running/planning`。
- Modify: `backend/app/api/ai.py`
  Purpose: 新增 `/chat/stream`，保留原 `/chat` 兼容接口。
- Modify: `backend/app/models/schemas.py`
  Purpose: 如需单独的 stream request/response schema，就在这里补齐；否则至少保持类型名和字段一致。

### Frontend

- Modify: `frontend/src/services/api.js`
  Purpose: 新增基于 `fetch` 的 stream 打开函数，复用现有 Bearer token。
- Create: `frontend/src/lib/sseFrameStream.js`
  Purpose: 解析 `text/event-stream` 帧，不依赖浏览器原生 `EventSource`。
- Create: `frontend/src/lib/sseFrameStream.test.js`
  Purpose: 覆盖跨 chunk 边界、空行分帧、JSON 反序列化。
- Create: `frontend/src/lib/agentChatStreaming.js`
  Purpose: AI 问答流式状态控制器。
- Create: `frontend/src/lib/agentChatStreaming.test.js`
  Purpose: 覆盖 delta/snapshot/completed/error 行为。
- Create: `frontend/src/lib/agentRuntimeStreaming.js`
  Purpose: 执行控制台 stream-first 状态控制器，负责 planner live text 与 runtime event 增量写入。
- Create: `frontend/src/lib/agentRuntimeStreaming.test.js`
  Purpose: 覆盖 runtime_event append、planner snapshot 覆盖、断流后回退 polling。
- Create: `frontend/src/components/agent/PlannerLivePanel.vue`
  Purpose: 在 execution ledger 顶部展示“规划生成中”的文本快照与当前阶段。
- Modify: `frontend/src/components/agent/AgentExecutionLedger.vue`
  Purpose: 接入 `PlannerLivePanel`。
- Modify: `frontend/src/components/agent/AgentChatPane.vue`
  Purpose: 支持 assistant 占位消息和持续流式更新。
- Modify: `frontend/src/views/AIAssistant.vue`
  Purpose: 接入问答流与 runtime session stream，并把 polling 降级为恢复路径。

### Tests

- Create: `tests/test_llm_streaming.py`
- Create: `tests/test_ai_chat_stream_api.py`
- Modify: `tests/test_goal_runtime_data_store.py`
- Modify: `tests/test_goal_runtime_api.py`
- Modify: `tests/test_frontend_ui_structure.py`
- Modify: `tests/test_real_data_only_structure.py`

---

### Task 1: Add Stream-Capable LLM Service Primitives

**Files:**
- Create: `tests/test_llm_streaming.py`
- Modify: `backend/app/services/llm.py`
- Create: `backend/app/services/sse.py`

- [ ] **Step 1: Write the failing LLM streaming tests**

Create `tests/test_llm_streaming.py`:

```python
import asyncio
import os
import sys
import types
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.llm import LLMService  # noqa: E402


class FakeChunk:
    def __init__(self, content):
        delta = types.SimpleNamespace(content=content)
        choice = types.SimpleNamespace(delta=delta)
        self.choices = [choice]


class FakeStreamingCompletions:
    def __init__(self, chunks):
        self.chunks = chunks
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)

        async def iterator():
            for item in self.chunks:
                yield FakeChunk(item)

        return iterator()


class FakeAsyncOpenAI:
    def __init__(self, chunks):
        self.chat = types.SimpleNamespace(
            completions=FakeStreamingCompletions(chunks)
        )


class LLMStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_stream_yields_incremental_text(self):
        service = LLMService("sk-demo", "https://api.example.com/v1", "demo-model")
        service.client = FakeAsyncOpenAI(["你好", "，世界"])

        chunks = []
        async for item in service.chat_stream("你好"):
            chunks.append(item)

        self.assertEqual(chunks, ["你好", "，世界"])
        self.assertTrue(service.supports_chat_stream())

    async def test_generate_control_plan_stream_yields_json_fragments(self):
        fragments = [
            '{"summary":"执行一次调度",',
            '"risk_level":"low","requires_confirmation":false,',
            '"warnings":[],"actions":[{"action":"run_schedule_once","target":{},"reason":"执行一次调度"}]}',
        ]
        service = LLMService("sk-demo", "https://api.example.com/v1", "demo-model")
        service.client = FakeAsyncOpenAI(fragments)

        chunks = []
        async for item in service.generate_control_plan_stream("执行一次调度", "{}"):
            chunks.append(item)

        self.assertEqual("".join(chunks), "".join(fragments))
        self.assertTrue(service.supports_control_plan_stream())
```

- [ ] **Step 2: Run the targeted test and verify it fails**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m pytest tests/test_llm_streaming.py -q
```

Expected: FAIL with `AttributeError` because `chat_stream()` / `generate_control_plan_stream()` / `supports_*_stream()` do not exist.

- [ ] **Step 3: Implement minimal LLM stream support and SSE frame encoding**

Update `backend/app/services/llm.py`:

```python
async def _stream_text(self, **kwargs):
    response = await self.client.chat.completions.create(stream=True, **kwargs)
    async for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta

def supports_chat_stream(self) -> bool:
    return True

def supports_control_plan_stream(self) -> bool:
    return True

async def chat_stream(self, user_message: str, gpu_context: str = ""):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if gpu_context:
        messages.append({"role": "system", "content": f"当前GPU集群实时状态：\n{gpu_context}"})
    messages.append({"role": "user", "content": user_message})
    async for item in self._stream_text(
        model=self.model,
        messages=messages,
        temperature=0.7,
        max_tokens=2000,
    ):
        yield item

async def generate_control_plan_stream(self, user_message: str, control_context: str):
    prompt = (
        f"用户指令：{user_message}\n\n"
        f"当前工作台上下文：\n{control_context}\n\n"
        "请输出结构化动作计划 JSON。"
    )
    async for item in self._stream_text(
        model=self.model,
        messages=[
            {"role": "system", "content": CONTROL_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=1500,
    ):
        yield item
```

Create `backend/app/services/sse.py`:

```python
from __future__ import annotations

import json


def encode_sse_event(event: str, data: dict) -> bytes:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")
```

- [ ] **Step 4: Run the targeted test and verify it passes**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m pytest tests/test_llm_streaming.py -q
```

Expected: PASS with `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_llm_streaming.py backend/app/services/llm.py backend/app/services/sse.py
git commit -m "feat: add llm streaming primitives"
```

---

### Task 2: Persist Runtime Live Phase And Planner Snapshot State

**Files:**
- Modify: `tests/test_goal_runtime_data_store.py`
- Modify: `backend/app/services/goal_runtime/data_store_support.py`
- Modify: `backend/app/services/data_store.py`
- Modify: `backend/app/services/goal_runtime/session_view.py`

- [ ] **Step 1: Write the failing data-store regression test**

Extend `tests/test_goal_runtime_data_store.py`:

```python
    async def test_data_store_overwrites_latest_planner_stream_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = DataStore(os.path.join(tmpdir, "runtime.db"))
            await store.init()
            try:
                await store.create_agent_session(
                    session_id="sess-2",
                    goal_json={"message": "执行一次调度"},
                    permission_mode="low",
                    status="running",
                    summary="执行一次调度",
                )
                await store.update_agent_session_status(
                    "sess-2",
                    "running",
                    "执行一次调度",
                    live_phase="planning",
                )
                await store.upsert_agent_stream_state(
                    "sess-2",
                    "planner",
                    latest_text="第一版计划",
                    latest_char_count=5,
                    revision=1,
                )
                await store.upsert_agent_stream_state(
                    "sess-2",
                    "planner",
                    latest_text="第二版计划",
                    latest_char_count=6,
                    revision=2,
                )

                session = await store.get_agent_session("sess-2")
                stream_state = await store.get_agent_stream_state("sess-2", "planner")
            finally:
                await store.close()

        self.assertEqual(session["live_phase"], "planning")
        self.assertEqual(stream_state["latest_text"], "第二版计划")
        self.assertEqual(stream_state["revision"], 2)
```

- [ ] **Step 2: Run the targeted test and verify it fails**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m pytest tests/test_goal_runtime_data_store.py -q
```

Expected: FAIL because `live_phase` and `upsert_agent_stream_state()` / `get_agent_stream_state()` do not exist yet.

- [ ] **Step 3: Implement live phase and overwrite-style stream state storage**

Update `backend/app/services/goal_runtime/data_store_support.py`:

```python
CREATE TABLE IF NOT EXISTS agent_runtime_sessions (
    session_id TEXT PRIMARY KEY,
    goal_json TEXT NOT NULL,
    permission_mode TEXT NOT NULL,
    status TEXT NOT NULL,
    live_phase TEXT NOT NULL DEFAULT 'planning',
    summary TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_runtime_stream_state (
    session_id TEXT NOT NULL,
    stream_kind TEXT NOT NULL,
    latest_text TEXT NOT NULL DEFAULT '',
    latest_char_count INTEGER NOT NULL DEFAULT 0,
    revision INTEGER NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL,
    PRIMARY KEY (session_id, stream_kind)
);
```

Add helpers:

```python
async def upsert_agent_stream_state(
    connection,
    session_id: str,
    stream_kind: str,
    *,
    latest_text: str,
    latest_char_count: int,
    revision: int,
) -> None:
    await connection.execute(
        """INSERT INTO agent_runtime_stream_state
           (session_id, stream_kind, latest_text, latest_char_count, revision, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(session_id, stream_kind) DO UPDATE SET
             latest_text = excluded.latest_text,
             latest_char_count = excluded.latest_char_count,
             revision = excluded.revision,
             updated_at = excluded.updated_at""",
        (session_id, stream_kind, latest_text, latest_char_count, revision, time.time()),
    )
    await connection.commit()

async def get_agent_stream_state(connection, session_id: str, stream_kind: str) -> dict | None:
    cursor = await connection.execute(
        """SELECT session_id, stream_kind, latest_text, latest_char_count, revision, updated_at
           FROM agent_runtime_stream_state WHERE session_id = ? AND stream_kind = ?""",
        (session_id, stream_kind),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None
```

Update `update_agent_session_status()` and wrappers to accept `live_phase`:

```python
async def update_agent_session_status(
    connection,
    session_id: str,
    status: str,
    summary: str,
    *,
    live_phase: str | None = None,
) -> None:
    if live_phase is None:
        await connection.execute(
            """UPDATE agent_runtime_sessions
               SET status = ?, summary = ?, updated_at = ?
               WHERE session_id = ?""",
            (status, summary, time.time(), session_id),
        )
    else:
        await connection.execute(
            """UPDATE agent_runtime_sessions
               SET status = ?, live_phase = ?, summary = ?, updated_at = ?
               WHERE session_id = ?""",
            (status, live_phase, summary, time.time(), session_id),
        )
    await connection.commit()
```

Update `backend/app/services/data_store.py` to expose:

```python
async def upsert_agent_stream_state(self, session_id, stream_kind, *, latest_text, latest_char_count, revision):
    await upsert_runtime_stream_state(
        require_runtime_db(self._db),
        session_id,
        stream_kind,
        latest_text=latest_text,
        latest_char_count=latest_char_count,
        revision=revision,
    )

async def get_agent_stream_state(self, session_id, stream_kind):
    return await load_runtime_stream_state(require_runtime_db(self._db), session_id, stream_kind)
```

Update `backend/app/services/goal_runtime/session_view.py`:

```python
def build_session_view(session: dict, events: list[dict], planner_stream: dict | None = None) -> dict:
    return {
        **session,
        "planner_stream": planner_stream,
        ...
    }
```

- [ ] **Step 4: Run the targeted test and verify it passes**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m pytest tests/test_goal_runtime_data_store.py -q
```

Expected: PASS with `2 passed` or more.

- [ ] **Step 5: Commit**

```bash
git add tests/test_goal_runtime_data_store.py backend/app/services/goal_runtime/data_store_support.py backend/app/services/data_store.py backend/app/services/goal_runtime/session_view.py
git commit -m "feat: persist runtime planner stream state"
```

---

### Task 3: Stream Goal Runtime Sessions From A Background Task

**Files:**
- Create: `backend/app/services/goal_runtime/session_stream.py`
- Modify: `backend/app/services/goal_runtime/reasoning_trace.py`
- Modify: `backend/app/services/goal_runtime/service.py`
- Modify: `backend/app/api/agent_runtime.py`
- Modify: `tests/test_goal_runtime_api.py`

- [ ] **Step 1: Write the failing runtime stream tests**

Extend `tests/test_goal_runtime_api.py`:

```python
class FakeGoalRuntimeService:
    ...
    async def stream_session(self, session_id):
        yield {"event": "session_started", "data": {"session_id": session_id}}
        yield {"event": "planner_snapshot", "data": {"latest_text": "正在生成计划", "revision": 1}}
        yield {"event": "completed", "data": {"session_id": session_id, "status": "awaiting_approval"}}

    async def start_session(self, message, permission_mode):
        self.calls.append(("start", message, permission_mode))
        return {"session_id": "sess-route", "status": "running", "live_phase": "planning"}
```

Add a route test:

```python
    async def test_stream_route_delegates_to_goal_runtime_service(self):
        fake_runtime = FakeGoalRuntimeService()
        fake_main = types.SimpleNamespace(app_state=types.SimpleNamespace(goal_runtime=fake_runtime))

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            response = await stream_agent_runtime_session("sess-route")
            chunks = []
            async for item in response.body_iterator:
                chunks.append(item.decode("utf-8"))

        self.assertIn("event: planner_snapshot", "".join(chunks))
        self.assertIn('"latest_text": "正在生成计划"', "".join(chunks))
```

Add a service-level test:

```python
    async def test_start_session_returns_running_planning_before_background_finishes(self):
        class SlowStreamingLLM:
            def supports_control_plan_stream(self):
                return True

            async def generate_control_plan_stream(self, _message, _context):
                yield '{"summary":"执行一次调度","risk_level":"low",'
                yield '"requires_confirmation":false,"warnings":[],"actions":[]}'

        runtime = GoalRuntimeService(
            store=store,
            registry=build_registry(),
            import_context=FakeImportContext(),
            runtime_status_reader=None,
            llm_service_reader=lambda: SlowStreamingLLM(),
            task_spawner=lambda coro: asyncio.create_task(coro),
        )

        result = await runtime.start_session("执行一次调度", "low")

        self.assertEqual(result["status"], "running")
        self.assertEqual(result["live_phase"], "planning")
```

- [ ] **Step 2: Run the targeted test and verify it fails**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m pytest tests/test_goal_runtime_api.py -q
```

Expected: FAIL because `stream_agent_runtime_session()` / `GoalRuntimeService.stream_session()` / `live_phase` do not exist.

- [ ] **Step 3: Implement per-session broker, background run loop, and stream route**

Create `backend/app/services/goal_runtime/session_stream.py`:

```python
from __future__ import annotations

import asyncio
from collections import defaultdict


class GoalRuntimeSessionStreamBroker:
    def __init__(self) -> None:
        self._subscribers = defaultdict(list)

    async def publish(self, session_id: str, event: str, data: dict) -> None:
        for queue in list(self._subscribers[session_id]):
            await queue.put({"event": event, "data": data})

    async def subscribe(self, session_id: str):
        queue = asyncio.Queue()
        self._subscribers[session_id].append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers[session_id].remove(queue)
```

Update `backend/app/services/goal_runtime/reasoning_trace.py` to accept callbacks:

```python
async def build_reasoning_trace(..., on_llm_delta=None, on_llm_snapshot=None):
    ...
    streamed_text = ""
    revision = 0
    if llm_service is not None and llm_service.supports_control_plan_stream():
        async for delta in llm_service.generate_control_plan_stream(message, _preview(request_payload, limit=1200)):
            streamed_text += delta
            if on_llm_delta is not None:
                await on_llm_delta(delta)
            if should_flush_snapshot(streamed_text, ...):
                revision += 1
                if on_llm_snapshot is not None:
                    await on_llm_snapshot(streamed_text, revision)
        llm_plan = json.loads(streamed_text)
```

Update `backend/app/services/goal_runtime/service.py` core shape:

```python
class GoalRuntimeService:
    def __init__(..., task_spawner=None, stream_broker=None):
        ...
        self.task_spawner = task_spawner or asyncio.create_task
        self.stream_broker = stream_broker or GoalRuntimeSessionStreamBroker()

    async def start_session(self, message: str, permission_mode: str) -> dict:
        session_id = uuid4().hex
        await self.store.create_agent_session(..., status="running", summary=message)
        await self.store.update_agent_session_status(session_id, "running", message, live_phase="planning")
        self.task_spawner(self._run_session(session_id, message, permission_mode))
        return {
            "session_id": session_id,
            "status": "running",
            "live_phase": "planning",
            "permission_mode": permission_mode,
            "summary": message,
            "requires_approval": False,
        }

    async def stream_session(self, session_id: str):
        async for item in self.stream_broker.subscribe(session_id):
            yield item
```

In `_run_session(...)`, publish:

```python
await self.stream_broker.publish(session_id, "session_started", {"session_id": session_id})
await self.stream_broker.publish(session_id, "planner_snapshot", {"latest_text": text, "revision": revision})
await self.stream_broker.publish(session_id, "runtime_event", event_payload)
await self.stream_broker.publish(session_id, "session_status", {"status": "awaiting_approval", "live_phase": "awaiting_approval"})
```

Update `backend/app/api/agent_runtime.py`:

```python
from fastapi.responses import StreamingResponse

from app.services.sse import encode_sse_event

@router.get("/sessions/{session_id}/stream")
async def stream_agent_runtime_session(session_id: str):
    from app.main import app_state

    session = await app_state.goal_runtime.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    async def iterator():
        async for item in app_state.goal_runtime.stream_session(session_id):
            yield encode_sse_event(item["event"], item["data"])

    return StreamingResponse(iterator(), media_type="text/event-stream")
```

- [ ] **Step 4: Run the targeted test and verify it passes**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m pytest tests/test_goal_runtime_api.py -q
```

Expected: PASS with the new stream route and immediate `running/planning` session creation behavior.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/goal_runtime/session_stream.py backend/app/services/goal_runtime/reasoning_trace.py backend/app/services/goal_runtime/service.py backend/app/api/agent_runtime.py tests/test_goal_runtime_api.py
git commit -m "feat: stream goal runtime sessions"
```

---

### Task 4: Add AI Chat Streaming API

**Files:**
- Create: `tests/test_ai_chat_stream_api.py`
- Modify: `backend/app/api/ai.py`
- Modify: `backend/app/models/schemas.py`

- [ ] **Step 1: Write the failing AI chat stream route test**

Create `tests/test_ai_chat_stream_api.py`:

```python
import json
import os
import sys
import types
import unittest
from unittest import mock


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.api.ai import chat_stream  # noqa: E402
from app.models.schemas import ChatRequest  # noqa: E402


class FakeLLM:
    def supports_chat_stream(self):
        return True

    async def chat_stream(self, _message, _context=""):
        yield "你好"
        yield "，世界"


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


class AIChatStreamRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_stream_returns_sse_frames(self):
        fake_state = types.SimpleNamespace(
            llm=FakeLLM(),
            agent=FakeAgent(),
            import_context=FakeImportContext(),
            privacy=FakePrivacy(),
        )
        fake_main = types.SimpleNamespace(app_state=fake_state)

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            response = await chat_stream(ChatRequest(message="你好"))
            chunks = []
            async for item in response.body_iterator:
                chunks.append(item.decode("utf-8"))

        text = "".join(chunks)
        self.assertIn("event: delta", text)
        self.assertIn("event: completed", text)
        self.assertIn("你好", text)
```

- [ ] **Step 2: Run the targeted test and verify it fails**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m pytest tests/test_ai_chat_stream_api.py -q
```

Expected: FAIL because `chat_stream()` route does not exist yet.

- [ ] **Step 3: Implement `/api/ai/chat/stream`**

Update `backend/app/api/ai.py`:

```python
from fastapi.responses import StreamingResponse

from app.services.sse import encode_sse_event

@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    from app.main import app_state
    if not app_state.llm:
        raise HTTPException(status_code=503, detail="LLM服务未配置")
    if not app_state.llm.supports_chat_stream():
        raise HTTPException(status_code=409, detail="当前模型不支持流式输出")

    gpu_context = await build_gpu_context(app_state)

    async def iterator():
        full_text = ""
        yield encode_sse_event("start", {"message": req.message})
        async for delta in app_state.llm.chat_stream(req.message, gpu_context):
            full_text += delta
            yield encode_sse_event("delta", {"text": delta})
            yield encode_sse_event("snapshot", {"text": full_text})
        yield encode_sse_event(
            "completed",
            {
                "reply": full_text,
                "suggestions": app_state.llm._extract_suggestions(full_text),
            },
        )

    return StreamingResponse(iterator(), media_type="text/event-stream")
```

Keep `chat()` unchanged for non-streaming callers.

- [ ] **Step 4: Run the targeted test and verify it passes**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m pytest tests/test_ai_chat_stream_api.py -q
```

Expected: PASS with `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_ai_chat_stream_api.py backend/app/api/ai.py backend/app/models/schemas.py
git commit -m "feat: add ai chat stream api"
```

---

### Task 5: Add Frontend SSE Frame Reader And Stream Controllers

**Files:**
- Modify: `frontend/src/services/api.js`
- Create: `frontend/src/lib/sseFrameStream.js`
- Create: `frontend/src/lib/sseFrameStream.test.js`
- Create: `frontend/src/lib/agentChatStreaming.js`
- Create: `frontend/src/lib/agentChatStreaming.test.js`
- Create: `frontend/src/lib/agentRuntimeStreaming.js`
- Create: `frontend/src/lib/agentRuntimeStreaming.test.js`

- [ ] **Step 1: Write the failing frontend stream helper tests**

Create `frontend/src/lib/sseFrameStream.test.js`:

```javascript
import test from 'node:test'
import assert from 'node:assert/strict'

import { parseSseFrames } from './sseFrameStream.js'

test('parseSseFrames reconstructs split frames across chunks', async () => {
  const frames = []
  for await (const item of parseSseFrames([
    'event: delta\ndata: {"text":"你',
    '好"}\n\nevent: completed\ndata: {"ok":true}\n\n',
  ])) {
    frames.push(item)
  }

  assert.deepEqual(frames, [
    { event: 'delta', data: { text: '你好' } },
    { event: 'completed', data: { ok: true } },
  ])
})
```

Create `frontend/src/lib/agentChatStreaming.test.js`:

```javascript
import test from 'node:test'
import assert from 'node:assert/strict'

import { reduceChatStreamEvent } from './agentChatStreaming.js'

test('reduceChatStreamEvent appends delta and overwrites snapshot', () => {
  let state = { text: '', suggestions: [] }
  state = reduceChatStreamEvent(state, { event: 'delta', data: { text: '你' } })
  state = reduceChatStreamEvent(state, { event: 'delta', data: { text: '好' } })
  state = reduceChatStreamEvent(state, { event: 'snapshot', data: { text: '你好，世界' } })

  assert.equal(state.text, '你好，世界')
})
```

Create `frontend/src/lib/agentRuntimeStreaming.test.js`:

```javascript
import test from 'node:test'
import assert from 'node:assert/strict'

import { reduceRuntimeStreamEvent } from './agentRuntimeStreaming.js'

test('reduceRuntimeStreamEvent appends runtime events and updates planner snapshot', () => {
  let state = {
    plannerLiveText: '',
    plannerLiveRevision: 0,
    runtimeEvents: [],
    runtimeSession: { status: 'running' },
  }

  state = reduceRuntimeStreamEvent(state, {
    event: 'planner_snapshot',
    data: { latest_text: '正在生成计划', revision: 1 },
  })
  state = reduceRuntimeStreamEvent(state, {
    event: 'runtime_event',
    data: { event_type: 'LLMRequestPrepared', payload: { summary: '准备请求' } },
  })

  assert.equal(state.plannerLiveText, '正在生成计划')
  assert.equal(state.runtimeEvents.length, 1)
})
```

- [ ] **Step 2: Run the targeted tests and verify they fail**

Run:

```bash
node --test frontend/src/lib/sseFrameStream.test.js frontend/src/lib/agentChatStreaming.test.js frontend/src/lib/agentRuntimeStreaming.test.js
```

Expected: FAIL because the new helper files do not exist yet.

- [ ] **Step 3: Implement SSE parser, stream reducers, and fetch wrappers**

Create `frontend/src/lib/sseFrameStream.js`:

```javascript
export async function* parseSseFrames(chunks) {
  let buffer = ''
  for await (const chunk of chunks) {
    buffer += chunk
    while (buffer.includes('\n\n')) {
      const boundary = buffer.indexOf('\n\n')
      const frame = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      const lines = frame.split('\n')
      const event = lines.find((line) => line.startsWith('event: '))?.slice(7) || 'message'
      const dataLine = lines.find((line) => line.startsWith('data: '))?.slice(6) || '{}'
      yield { event, data: JSON.parse(dataLine) }
    }
  }
}
```

Create `frontend/src/lib/agentChatStreaming.js`:

```javascript
export function reduceChatStreamEvent(state, frame) {
  if (frame.event === 'delta') {
    return { ...state, text: `${state.text}${frame.data.text || ''}` }
  }
  if (frame.event === 'snapshot') {
    return { ...state, text: frame.data.text || '' }
  }
  if (frame.event === 'completed') {
    return {
      ...state,
      text: frame.data.reply || state.text,
      suggestions: frame.data.suggestions || [],
      completed: true,
    }
  }
  return state
}
```

Create `frontend/src/lib/agentRuntimeStreaming.js`:

```javascript
export function reduceRuntimeStreamEvent(state, frame) {
  if (frame.event === 'planner_snapshot') {
    return {
      ...state,
      plannerLiveText: frame.data.latest_text || '',
      plannerLiveRevision: Number(frame.data.revision || 0),
    }
  }
  if (frame.event === 'runtime_event') {
    return {
      ...state,
      runtimeEvents: [...state.runtimeEvents, frame.data],
    }
  }
  if (frame.event === 'session_status') {
    return {
      ...state,
      runtimeSession: { ...state.runtimeSession, ...frame.data },
    }
  }
  return state
}
```

Update `frontend/src/services/api.js`:

```javascript
async function openAuthorizedEventStream(url, payload = null) {
  const token = readSessionToken()
  const response = await fetch(url, {
    method: payload ? 'POST' : 'GET',
    headers: {
      'Accept': 'text/event-stream',
      ...(payload ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: payload ? JSON.stringify(payload) : undefined,
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `stream request failed: ${response.status}`)
  }
  return response
}

export const openAiChatStream = (message) =>
  openAuthorizedEventStream('/api/ai/chat/stream', { message })

export const openAgentRuntimeSessionStream = (sessionId) =>
  openAuthorizedEventStream(`/api/agent-runtime/sessions/${sessionId}/stream`)
```

- [ ] **Step 4: Run the targeted tests and verify they pass**

Run:

```bash
node --test frontend/src/lib/sseFrameStream.test.js frontend/src/lib/agentChatStreaming.test.js frontend/src/lib/agentRuntimeStreaming.test.js
```

Expected: PASS with `3 pass`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/api.js frontend/src/lib/sseFrameStream.js frontend/src/lib/sseFrameStream.test.js frontend/src/lib/agentChatStreaming.js frontend/src/lib/agentChatStreaming.test.js frontend/src/lib/agentRuntimeStreaming.js frontend/src/lib/agentRuntimeStreaming.test.js
git commit -m "feat: add frontend stream controllers"
```

---

### Task 6: Wire Streaming Into AIAssistant And Execution Ledger

**Files:**
- Create: `frontend/src/components/agent/PlannerLivePanel.vue`
- Modify: `frontend/src/components/agent/AgentExecutionLedger.vue`
- Modify: `frontend/src/components/agent/AgentChatPane.vue`
- Modify: `frontend/src/views/AIAssistant.vue`
- Modify: `tests/test_frontend_ui_structure.py`
- Modify: `tests/test_real_data_only_structure.py`

- [ ] **Step 1: Write the failing structure tests**

Extend `tests/test_frontend_ui_structure.py`:

```python
    def test_ai_assistant_uses_streaming_live_panel_and_stream_apis(self):
        text = (ROOT / "frontend/src/views/AIAssistant.vue").read_text(encoding="utf-8")
        api_text = (ROOT / "frontend/src/services/api.js").read_text(encoding="utf-8")

        self.assertIn("PlannerLivePanel", text)
        self.assertIn("openAiChatStream", api_text)
        self.assertIn("openAgentRuntimeSessionStream", api_text)
```

Extend `tests/test_real_data_only_structure.py`:

```python
    def test_ai_assistant_streaming_ui_uses_runtime_session_stream(self):
        ai_text = (ROOT / "frontend/src/views/AIAssistant.vue").read_text(encoding="utf-8")

        self.assertIn("plannerLiveText", ai_text)
        self.assertIn("openAgentRuntimeSessionStream", ai_text)
        self.assertNotIn("EventSource(", ai_text)
```

- [ ] **Step 2: Run the structure tests and verify they fail**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure tests.test_real_data_only_structure -q
```

Expected: FAIL because `PlannerLivePanel` and the stream API wrappers are not yet wired into `AIAssistant.vue`.

- [ ] **Step 3: Implement planner live panel and hook up chat/runtime streaming**

Create `frontend/src/components/agent/PlannerLivePanel.vue`:

```vue
<script setup>
defineProps({
  active: { type: Boolean, default: false },
  phase: { type: String, default: 'planning' },
  text: { type: String, default: '' },
  error: { type: String, default: '' },
})
</script>

<template>
  <section class="planner-live-panel" :class="{ 'planner-live-panel--active': active }">
    <header class="planner-live-panel__head">
      <h4>规划生成中</h4>
      <span>{{ phase }}</span>
    </header>
    <pre class="planner-live-panel__body">{{ text || '等待规划输出...' }}</pre>
    <div v-if="error" class="planner-live-panel__error">{{ error }}</div>
  </section>
</template>
```

Update `frontend/src/components/agent/AgentExecutionLedger.vue`:

```vue
<script setup>
import PlannerLivePanel from './PlannerLivePanel.vue'
...
defineProps({
  plannerLiveText: { type: String, default: '' },
  plannerLivePhase: { type: String, default: 'planning' },
  plannerStreamActive: { type: Boolean, default: false },
  plannerStreamError: { type: String, default: '' },
})
</script>

<template>
  <section class="agent-execution-ledger tech-card">
    <AgentRunOverviewBar :overview="overview" />
    <PlannerLivePanel
      :active="plannerStreamActive"
      :phase="plannerLivePhase"
      :text="plannerLiveText"
      :error="plannerStreamError"
    />
    ...
  </section>
</template>
```

Update `frontend/src/views/AIAssistant.vue` with explicit streaming state:

```javascript
const plannerStreamActive = ref(false)
const plannerLiveText = ref('')
const plannerLiveRevision = ref(0)
const plannerLivePhase = ref('planning')
const plannerStreamError = ref('')

async function startChatStreaming(message) {
  const response = await openAiChatStream(message)
  for await (const frame of parseSseFrames(readResponseTextChunks(response))) {
    chatState.value = reduceChatStreamEvent(chatState.value, frame)
  }
}

async function connectRuntimeStream(sessionId) {
  plannerStreamActive.value = true
  const response = await openAgentRuntimeSessionStream(sessionId)
  for await (const frame of parseSseFrames(readResponseTextChunks(response))) {
    const nextState = reduceRuntimeStreamEvent({
      plannerLiveText: plannerLiveText.value,
      plannerLiveRevision: plannerLiveRevision.value,
      runtimeEvents: runtimeEvents.value,
      runtimeSession: runtimeSession.value || {},
    }, frame)
    plannerLiveText.value = nextState.plannerLiveText
    plannerLiveRevision.value = nextState.plannerLiveRevision
    runtimeEvents.value = nextState.runtimeEvents
    runtimeSession.value = nextState.runtimeSession
  }
}

async function generateControlPlan(message = controlInput.value.trim()) {
  ...
  const { data } = await startAgentRuntimeSession(message, controlPermissionMode.value)
  mergeRuntimeSession(data)
  await connectRuntimeStream(data.session_id)
}
```

Keep `createAgentRuntimeSessionPolling()` only for recovery:

```javascript
function handleRuntimeStreamFailure(error) {
  plannerStreamError.value = error.message
  plannerStreamActive.value = false
  runtimePolling.start(() => refreshRuntimeSession(runtimeSession.value?.session_id))
}
```

- [ ] **Step 4: Run structure tests, stream helper tests, and build**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure tests.test_real_data_only_structure -q
node --test frontend/src/lib/sseFrameStream.test.js frontend/src/lib/agentChatStreaming.test.js frontend/src/lib/agentRuntimeStreaming.test.js frontend/src/lib/agentExecutionLedger.test.js frontend/src/lib/agentRuntimeSessionPolling.test.js
npm --prefix frontend run build
```

Expected: PASS with the new live panel and stream helpers wired into the assistant view.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/agent/PlannerLivePanel.vue frontend/src/components/agent/AgentExecutionLedger.vue frontend/src/components/agent/AgentChatPane.vue frontend/src/views/AIAssistant.vue tests/test_frontend_ui_structure.py tests/test_real_data_only_structure.py
git commit -m "feat: wire ai assistant streaming ui"
```

---

### Task 7: Run Full Verification And Land The Refactor Cleanly

**Files:**
- Modify: `docs/superpowers/specs/2026-04-09-agent-runtime-streaming-design.md` only if implementation exposed a real mismatch
- Modify: `push日志.txt` only if the user explicitly asks for this round’s push log

- [ ] **Step 1: Run the full backend regression suite**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m pytest tests/test_llm_streaming.py tests/test_ai_chat_stream_api.py tests/test_goal_runtime_data_store.py tests/test_goal_runtime_api.py tests/test_goal_runtime_models.py tests/test_goal_runtime_capabilities.py tests/test_goal_runtime_planner.py tests/test_goal_runtime_supervisor.py backend/tests/test_ai_control.py tests/test_scheduler.py tests/test_runtime_snapshot_routes.py -q
```

Expected: PASS with all targeted runtime and streaming tests green.

- [ ] **Step 2: Run frontend and structure verification**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure tests.test_real_data_only_structure -q
node --test frontend/src/lib/sseFrameStream.test.js frontend/src/lib/agentChatStreaming.test.js frontend/src/lib/agentRuntimeStreaming.test.js frontend/src/lib/agentExecutionLedger.test.js frontend/src/lib/agentRuntimeSessionPolling.test.js
npm --prefix frontend run build
```

Expected: PASS with no structure regressions and a successful production build.

- [ ] **Step 3: Compile backend modules**

Run:

```bash
./.venv/Scripts/python.exe -m compileall backend/app
```

Expected: PASS with no syntax errors.

- [ ] **Step 4: Commit the final refactor**

```bash
git add backend/app/services/llm.py backend/app/services/sse.py backend/app/services/goal_runtime/data_store_support.py backend/app/services/data_store.py backend/app/services/goal_runtime/session_stream.py backend/app/services/goal_runtime/session_view.py backend/app/services/goal_runtime/reasoning_trace.py backend/app/services/goal_runtime/service.py backend/app/api/agent_runtime.py backend/app/api/ai.py backend/app/models/schemas.py tests/test_llm_streaming.py tests/test_ai_chat_stream_api.py tests/test_goal_runtime_data_store.py tests/test_goal_runtime_api.py frontend/src/services/api.js frontend/src/lib/sseFrameStream.js frontend/src/lib/sseFrameStream.test.js frontend/src/lib/agentChatStreaming.js frontend/src/lib/agentChatStreaming.test.js frontend/src/lib/agentRuntimeStreaming.js frontend/src/lib/agentRuntimeStreaming.test.js frontend/src/components/agent/PlannerLivePanel.vue frontend/src/components/agent/AgentExecutionLedger.vue frontend/src/components/agent/AgentChatPane.vue frontend/src/views/AIAssistant.vue tests/test_frontend_ui_structure.py tests/test_real_data_only_structure.py
git commit -m "feat: stream ai assistant and goal runtime sessions"
```

---

## Coverage Check

- 问答助手真实流式输出：Task 1, Task 4, Task 5, Task 6 cover `LLMService.chat_stream()`、`/api/ai/chat/stream`、前端 parser 和 UI 接入。
- 执行控制台先创建 session 再推流：Task 2 and Task 3 cover `live_phase`、stream state、后台任务和 `/sessions/{id}/stream`。
- 规划文本与结构化账本并存：Task 3 and Task 6 cover `planner_snapshot` + `runtime_event` 双轨输出和 `PlannerLivePanel`。
- 只持久化最新快照与最终结果：Task 2 and Task 3 cover overwrite-style `agent_runtime_stream_state` plus final runtime events.
- 不使用原生 `EventSource`：Task 5 and Task 6 explicitly use `fetch + ReadableStream`.
- stream-first, polling-recovery-only：Task 5 and Task 6 cover runtime stream controller + existing polling fallback.

## Placeholder Scan

- No `TODO`, `TBD`, or “similar to Task N”.
- All code steps include explicit code snippets, file paths, and commands.
- Property names are consistent across tasks:
  - `live_phase`
  - `planner_stream`
  - `plannerLiveText`
  - `openAiChatStream`
  - `openAgentRuntimeSessionStream`
