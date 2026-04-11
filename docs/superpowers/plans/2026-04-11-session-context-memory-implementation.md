# Session Context Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让同一 `session_id` 下的历史对话文本与 runtime 关键事件真正回灌到后续的判路、聊天和 runtime 规划调用中。

**Architecture:** 新增一个后端 `session_context` 构建器，从 session 记录与事件历史中提取“最近原文 + 更早摘要 + runtime 摘要”，再通过统一格式化函数注入到三条 LLM 调用链。前端只负责把当前 `session_id` 继续传给 `/api/ai/workbench/dispatch` 和 `/api/ai/chat/stream`，不在前端拼上下文。

**Tech Stack:** FastAPI, Pydantic, asyncio, Vue 3 composables, Axios/fetch SSE, Python `unittest`

---

## File Structure

- Create: `backend/app/services/goal_runtime/session_context.py`
  - 负责把 session + events 转换成结构化上下文对象，并格式化为稳定 prompt 文本。
- Modify: `backend/app/services/goal_runtime/service.py`
  - 暴露 `build_session_context_payload()` 给 runtime 规划和 AI API 复用。
- Modify: `backend/app/services/goal_runtime/reasoning_trace.py`
  - 将 session context 纳入 `request_payload` 和 LLM 控制规划输入。
- Modify: `backend/app/services/llm.py`
  - 为 `chat()`、`chat_stream()`、`dispatch_workbench_message()` 添加 `session_context` 入参，并统一注入 prompt。
- Modify: `backend/app/api/ai.py`
  - 从请求中接收 `session_id`，按需构建 session context 并传入 LLM 层。
- Modify: `backend/app/models/schemas.py`
  - 为 `ChatRequest` 和 `AiWorkbenchDispatchRequest` 添加可选 `session_id`。
- Modify: `frontend/src/services/api.js`
  - 把 `session_id` 传给 `/api/ai/workbench/dispatch` 和 `/api/ai/chat/stream`。
- Modify: `frontend/src/composables/useAiAssistantWorkbench.js`
  - 在已有会话中提交新消息时，把 `previousSessionId` 传给判路和聊天流调用。
- Test: `tests/test_goal_runtime_session_context.py`
  - 覆盖上下文构建、摘要、压缩和显式超预算错误。
- Test: `tests/test_goal_runtime_api.py`
  - 覆盖 runtime 规划链复用旧 session 时携带历史上下文。
- Test: `tests/test_ai_workbench_dispatch_api.py`
  - 覆盖判路 API 传递 session context。
- Test: `tests/test_ai_chat_stream_api.py`
  - 覆盖聊天流 API 传递 session context。
- Test: `tests/test_llm_streaming.py`
  - 覆盖 LLMService 在流式聊天中把 session context 注入 OpenAI 请求。

### Task 1: Build The Session Context Module

**Files:**
- Create: `backend/app/services/goal_runtime/session_context.py`
- Create: `tests/test_goal_runtime_session_context.py`

- [ ] **Step 1: Write the failing tests**

```python
import os
import sys
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.goal_runtime.session_context import (  # noqa: E402
    SessionContextBudgetError,
    build_session_context_payload,
    format_session_context_for_prompt,
)


SESSION = {
    "session_id": "sess-memory",
    "status": "completed",
    "live_phase": "completed",
    "summary": "继续刚才那个任务",
    "goal_json": {
        "message": "第一轮问题",
        "raw_message": "第一轮问题",
        "last_message": "继续刚才那个任务",
    },
}

EVENTS = [
    {
        "event_type": "UserMessageSubmitted",
        "payload": {"content": "第一轮问题"},
        "round_index": 1,
        "sequence": 0,
        "source": "chat",
    },
    {
        "event_type": "AssistantMessageGenerated",
        "payload": {"content": "第一轮回答"},
        "round_index": 1,
        "sequence": 1,
        "source": "chat",
    },
    {
        "event_type": "PlanCreated",
        "payload": {"summary": "准备将 GPU 3 功耗上限设置为 220W"},
        "round_index": 2,
        "sequence": 2,
        "source": "planner",
    },
    {
        "event_type": "AwaitingApproval",
        "payload": {"summary": "等待审批"},
        "round_index": 2,
        "sequence": 3,
        "source": "runtime",
    },
    {
        "event_type": "SessionCompleted",
        "payload": {"summary": "set_power_limit GPU 3 -> 220W succeeded"},
        "round_index": 2,
        "sequence": 4,
        "source": "runtime",
    },
    {
        "event_type": "UserMessageSubmitted",
        "payload": {"content": "继续刚才那个任务"},
        "round_index": 3,
        "sequence": 0,
        "source": "chat",
    },
]


class SessionContextBuilderTests(unittest.TestCase):
    def test_build_payload_keeps_recent_rounds_and_summarizes_older_ones(self):
        payload = build_session_context_payload(
            SESSION,
            EVENTS,
            "继续刚才那个任务",
            recent_round_limit=1,
            max_prompt_chars=1200,
        )

        self.assertEqual(payload["session_id"], "sess-memory")
        self.assertEqual(payload["current_request"]["message"], "继续刚才那个任务")
        self.assertEqual(len(payload["recent_messages"]), 1)
        self.assertEqual(payload["recent_messages"][0]["round_index"], 3)
        self.assertEqual(payload["historical_summary"]["round_count"], 2)
        self.assertIn("第一轮问题", "\n".join(payload["historical_summary"]["summary_lines"]))
        self.assertEqual(payload["runtime_summary"]["latest_plan"], "准备将 GPU 3 功耗上限设置为 220W")
        self.assertEqual(
            payload["runtime_summary"]["latest_execution"],
            "set_power_limit GPU 3 -> 220W succeeded",
        )

    def test_prompt_format_includes_summary_recent_rounds_and_runtime_summary(self):
        payload = build_session_context_payload(
            SESSION,
            EVENTS,
            "继续刚才那个任务",
            recent_round_limit=1,
            max_prompt_chars=1200,
        )

        prompt = format_session_context_for_prompt(payload)
        self.assertIn("会话历史摘要：", prompt)
        self.assertIn("最近对话原文：", prompt)
        self.assertIn("运行态摘要：", prompt)
        self.assertIn("第一轮问题", prompt)
        self.assertIn("set_power_limit GPU 3 -> 220W succeeded", prompt)

    def test_builder_raises_when_budget_is_still_exceeded_after_summary_compression(self):
        with self.assertRaises(SessionContextBudgetError):
            build_session_context_payload(
                SESSION,
                EVENTS * 12,
                "继续刚才那个任务",
                recent_round_limit=2,
                max_prompt_chars=80,
            )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cmd.exe /d /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_goal_runtime_session_context.py -q"
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.goal_runtime.session_context'`

- [ ] **Step 3: Write the minimal implementation**

```python
from __future__ import annotations

from dataclasses import dataclass


DEFAULT_RECENT_ROUND_LIMIT = 3
DEFAULT_SUMMARY_LINE_LIMIT = 6
DEFAULT_MAX_PROMPT_CHARS = 6000
RUNTIME_SUMMARY_EVENT_TYPES = {
    "PlanCreated",
    "AwaitingApproval",
    "SessionCompleted",
    "SessionFailed",
    "LLMCallFailed",
}


@dataclass(slots=True)
class SessionContextBudgetError(ValueError):
    message: str

    def __str__(self) -> str:
        return self.message


def _group_round_messages(events: list[dict]) -> list[dict]:
    grouped = {}
    for event in events:
        if event.get("event_type") not in {"UserMessageSubmitted", "AssistantMessageGenerated"}:
            continue
        round_index = int(event.get("round_index") or 0)
        bucket = grouped.setdefault(round_index, {"round_index": round_index, "messages": []})
        role = "user" if event["event_type"] == "UserMessageSubmitted" else "assistant"
        content = str(event.get("payload", {}).get("content") or "").strip()
        if content:
            bucket["messages"].append({"role": role, "content": content})
    return [grouped[key] for key in sorted(grouped)]


def _summarize_historical_rounds(rounds: list[dict], limit: int) -> dict:
    summary_lines = []
    for item in rounds:
        snippets = []
        for message in item["messages"]:
            prefix = "用户" if message["role"] == "user" else "助手"
            snippets.append(f"{prefix}：{message['content']}")
        if snippets:
            summary_lines.append("；".join(snippets))
    return {
        "round_count": len(rounds),
        "summary_lines": summary_lines[:limit],
        "entities": {
            "gpu_indexes": sorted(
                {
                    int(token)
                    for line in summary_lines
                    for token in __import__("re").findall(r"GPU\\s*(\\d+)", line, __import__("re").IGNORECASE)
                }
            ),
            "job_ids": sorted(
                {
                    token
                    for line in summary_lines
                    for token in __import__("re").findall(r"(job-[A-Za-z0-9_-]+)", line)
                }
            ),
            "pids": sorted(
                {
                    int(token)
                    for line in summary_lines
                    for token in __import__("re").findall(r"PID\\s*(\\d+)", line, __import__("re").IGNORECASE)
                }
            ),
            "nodes": [],
            "queues": [],
        },
        "constraints": [],
    }


def _summarize_runtime(events: list[dict], session: dict) -> dict:
    latest_plan = ""
    approval_status = ""
    latest_execution = ""
    latest_failure = ""
    for event in events:
        if event.get("event_type") == "PlanCreated":
            latest_plan = str(event.get("payload", {}).get("summary") or latest_plan)
        if event.get("event_type") == "AwaitingApproval":
            approval_status = "awaiting_approval"
        if event.get("event_type") == "SessionCompleted":
            latest_execution = str(event.get("payload", {}).get("summary") or latest_execution)
            if not approval_status:
                approval_status = "approved"
        if event.get("event_type") in {"SessionFailed", "LLMCallFailed"}:
            latest_failure = str(
                event.get("payload", {}).get("error")
                or event.get("payload", {}).get("summary")
                or latest_failure
            )
    return {
        "latest_plan": latest_plan,
        "approval_status": approval_status,
        "latest_execution": latest_execution,
        "latest_failure": latest_failure,
        "live_phase": str(session.get("live_phase") or session.get("status") or ""),
    }


def format_session_context_for_prompt(payload: dict) -> str:
    lines = ["会话历史摘要："]
    for item in payload["historical_summary"]["summary_lines"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("最近对话原文：")
    for round_item in payload["recent_messages"]:
        lines.append(f"第 {round_item['round_index']} 轮")
        for message in round_item["messages"]:
            role = "用户" if message["role"] == "user" else "助手"
            lines.append(f"{role}：{message['content']}")
    lines.append("")
    lines.append("运行态摘要：")
    lines.append(f"- 最近计划：{payload['runtime_summary']['latest_plan'] or '无'}")
    lines.append(f"- 审批状态：{payload['runtime_summary']['approval_status'] or '无'}")
    lines.append(f"- 最近成功执行：{payload['runtime_summary']['latest_execution'] or '无'}")
    lines.append(f"- 最近失败原因：{payload['runtime_summary']['latest_failure'] or '无'}")
    return "\n".join(lines).strip()


def build_session_context_payload(
    session: dict | None,
    events: list[dict],
    current_message: str,
    *,
    recent_round_limit: int = DEFAULT_RECENT_ROUND_LIMIT,
    max_prompt_chars: int = DEFAULT_MAX_PROMPT_CHARS,
) -> dict:
    session_obj = dict(session or {})
    rounds = _group_round_messages(events)
    recent_messages = rounds[-recent_round_limit:]
    historical_rounds = rounds[:-recent_round_limit] if recent_round_limit else rounds
    payload = {
        "session_id": str(session_obj.get("session_id") or ""),
        "current_request": {"message": current_message},
        "recent_messages": recent_messages,
        "historical_summary": _summarize_historical_rounds(
            historical_rounds,
            DEFAULT_SUMMARY_LINE_LIMIT,
        ),
        "runtime_summary": _summarize_runtime(events, session_obj),
    }
    prompt = format_session_context_for_prompt(payload)
    if len(prompt) > max_prompt_chars:
        payload["historical_summary"]["summary_lines"] = payload["historical_summary"]["summary_lines"][:1]
        prompt = format_session_context_for_prompt(payload)
    if len(prompt) > max_prompt_chars:
        raise SessionContextBudgetError(
            "session context exceeds safe prompt budget after compression"
        )
    return payload
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
cmd.exe /d /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_goal_runtime_session_context.py -q"
```

Expected: `Ran 3 tests` and `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/goal_runtime/session_context.py tests/test_goal_runtime_session_context.py
git commit -m "feat: add session context builder"
```

### Task 2: Inject Session Context Into Runtime Planning

**Files:**
- Modify: `backend/app/services/goal_runtime/service.py`
- Modify: `backend/app/services/goal_runtime/reasoning_trace.py`
- Modify: `tests/test_goal_runtime_api.py`

- [ ] **Step 1: Write the failing runtime-context test**

```python
    async def test_start_session_reuses_history_in_llm_request_context(self):
        store = FakeStore()
        runtime = GoalRuntimeService(
            store=store,
            registry=build_registry(),
            import_context=FakeImportContext(),
            runtime_status_reader=None,
            llm_service_reader=lambda: None,
            task_spawner=lambda coro: asyncio.create_task(coro),
        )

        created = await runtime.append_chat_turn(
            "第一轮问题",
            "第一轮回答",
            "low",
        )

        planning_llm = FakeLLM(
            {
                "summary": "继续执行 GPU 0 的调度计划",
                "risk_level": "low",
                "requires_confirmation": False,
                "warnings": [],
                "actions": [],
            }
        )
        runtime.llm_service_reader = lambda: planning_llm

        await runtime.start_session(
            "继续刚才那个任务",
            "low",
            session_id=created["session"]["session_id"],
        )
        await runtime.wait_for_idle()

        self.assertIn("第一轮问题", planning_llm.calls[-1][1])
        self.assertIn("第一轮回答", planning_llm.calls[-1][1])
        self.assertIn("继续刚才那个任务", planning_llm.calls[-1][1])

        events = await runtime.get_events(created["session"]["session_id"])
        prepared = next(
            item for item in events if item["event_type"] == "LLMRequestPrepared"
        )
        self.assertIn("session_context", prepared["payload"]["prompt_full"])
        self.assertEqual(
            prepared["payload"]["prompt_full"]["session_context"]["current_request"]["message"],
            "继续刚才那个任务",
        )
```

- [ ] **Step 2: Run the runtime API tests to verify the new assertion fails**

Run:

```bash
cmd.exe /d /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_goal_runtime_api.py -q"
```

Expected: FAIL because `planning_llm.calls[-1][1]` does not include prior round messages and `LLMRequestPrepared` has no `session_context`

- [ ] **Step 3: Implement the minimal runtime injection**

```python
# backend/app/services/goal_runtime/service.py
from app.services.goal_runtime.session_context import build_session_context_payload

    async def build_session_context_payload(
        self,
        session_id: str,
        current_message: str,
    ) -> dict:
        session = await self.store.get_agent_session(session_id)
        if session is None:
            raise ValueError(f"session not found: {session_id}")
        events = await self.store.get_agent_events(session_id)
        return build_session_context_payload(
            session,
            events,
            current_message,
        )

    async def start_session(
        self,
        message: str,
        permission_mode: str,
        *,
        session_id: str = "",
    ) -> dict:
        session_key = str(session_id or "").strip() or uuid4().hex
        round_index = 1
        session_context = None
        if session_id:
            round_index = await self._prepare_session(session_key, message, permission_mode)
            session_context = await self.build_session_context_payload(session_key, message)
        else:
            await self.store.create_agent_session(
                session_key,
                self._initial_goal_json(message),
                permission_mode,
                "running",
                message,
            )
        await self.session_runtime.append_event(
            session_key,
            "UserMessageSubmitted",
            {"content": message},
            round_index=round_index,
            sequence=0,
            source="chat",
        )
        task = self.task_spawner(
            self.session_runtime.run_session(
                session_key,
                message,
                permission_mode,
                round_index=round_index,
                session_context=session_context,
            )
        )
        self._track_task(task)
        return {
            "session_id": session_key,
            "status": "running",
            "live_phase": "planning",
            "permission_mode": permission_mode,
            "summary": message,
            "current_round": round_index,
            "requires_approval": False,
            "pending_approval": None,
            "event_types": [],
        }

# backend/app/services/goal_runtime/session_runtime.py
# Update the existing build_reasoning_trace call inside run_session():
        planning_result, trace_events = await build_reasoning_trace(
            message=message,
            permission_mode=permission_mode,
            registry=self.registry,
            llm_service=self.llm_service_reader(),
            round_index=round_index,
            session_context=session_context,
            on_llm_snapshot=lambda text, revision: self.publish_planner_snapshot(
                session_id,
                text,
                revision,
            ),
        )

# backend/app/services/goal_runtime/reasoning_trace.py
from app.services.goal_runtime.session_context import format_session_context_for_prompt

async def build_reasoning_trace(
    *,
    message: str,
    permission_mode: str,
    registry,
    llm_service,
    round_index: int = DEFAULT_TRACE_ROUND_INDEX,
    session_context: dict | None = None,
    on_llm_delta: PlanDeltaCallback | None = None,
    on_llm_snapshot: PlanSnapshotCallback | None = None,
) -> tuple[dict, list[dict]]:
    request_payload = {
        "message": message,
        "permission_mode": permission_mode,
        "snapshot": snapshot,
        "session_context": session_context or {},
    }
    llm_plan = await _load_llm_plan(
        llm_service,
        message,
        _preview(request_payload, limit=1200)
        + "\n\n会话记忆：\n"
        + format_session_context_for_prompt(session_context or {
            "session_id": "",
            "current_request": {"message": message},
            "recent_messages": [],
            "historical_summary": {"round_count": 0, "summary_lines": [], "entities": {"gpu_indexes": [], "job_ids": [], "pids": [], "nodes": [], "queues": []}, "constraints": []},
            "runtime_summary": {"latest_plan": "", "approval_status": "", "latest_execution": "", "latest_failure": "", "live_phase": ""},
        }),
        on_llm_delta,
        on_llm_snapshot,
    )
```

- [ ] **Step 4: Run the runtime API tests to verify they pass**

Run:

```bash
cmd.exe /d /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_goal_runtime_api.py -q"
```

Expected: `Ran` count increases by `1` and `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/goal_runtime/service.py backend/app/services/goal_runtime/session_runtime.py backend/app/services/goal_runtime/reasoning_trace.py tests/test_goal_runtime_api.py
git commit -m "feat: inject session context into runtime planning"
```

### Task 3: Wire Session Context Through AI Chat And Dispatch

**Files:**
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/api/ai.py`
- Modify: `backend/app/services/llm.py`
- Modify: `frontend/src/services/api.js`
- Modify: `frontend/src/composables/useAiAssistantWorkbench.js`
- Modify: `tests/test_ai_workbench_dispatch_api.py`
- Modify: `tests/test_ai_chat_stream_api.py`
- Modify: `tests/test_llm_streaming.py`

- [ ] **Step 1: Write the failing API and streaming tests**

```python
# tests/test_ai_workbench_dispatch_api.py
class FakeGoalRuntime:
    def __init__(self):
        self.calls = []

    async def build_session_context_payload(self, session_id, current_message):
        self.calls.append((session_id, current_message))
        return {
            "session_id": session_id,
            "current_request": {"message": current_message},
            "recent_messages": [
                {
                    "round_index": 1,
                    "messages": [
                        {"role": "user", "content": "第一轮问题"},
                        {"role": "assistant", "content": "第一轮回答"},
                    ],
                }
            ],
            "historical_summary": {
                "round_count": 0,
                "summary_lines": [],
                "entities": {"gpu_indexes": [], "job_ids": [], "pids": [], "nodes": [], "queues": []},
                "constraints": [],
            },
            "runtime_summary": {
                "latest_plan": "",
                "approval_status": "",
                "latest_execution": "",
                "latest_failure": "",
                "live_phase": "completed",
            },
        }

class FakeLLM:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    async def dispatch_workbench_message(self, message, gpu_context="", session_context=""):
        self.calls.append((message, gpu_context, session_context))
        if self.error:
            raise self.error
        return dict(self.result)

    async def test_dispatch_passes_formatted_session_context(self):
        fake_llm = FakeLLM({"route_kind": "chat", "reply_mode": "stream"})
        fake_goal_runtime = FakeGoalRuntime()
        fake_state = types.SimpleNamespace(
            llm=fake_llm,
            goal_runtime=fake_goal_runtime,
            agent=FakeAgent(),
            import_context=FakeImportContext(),
            privacy=FakePrivacy(),
        )
        fake_main = types.SimpleNamespace(app_state=fake_state)

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            await dispatch_workbench_message(
                AiWorkbenchDispatchRequest(
                    message="继续刚才那个任务",
                    session_id="sess-route",
                )
            )

        self.assertEqual(fake_goal_runtime.calls[0], ("sess-route", "继续刚才那个任务"))
        self.assertIn("第一轮问题", fake_llm.calls[0][2])
        self.assertIn("第一轮回答", fake_llm.calls[0][2])

# tests/test_ai_chat_stream_api.py
class FakeLLM:
    def supports_chat_stream(self):
        return True

    def __init__(self):
        self.calls = []

    async def chat_stream(self, message, gpu_context="", session_context=""):
        self.calls.append((message, gpu_context, session_context))
        yield "你好"
        yield "，世界"

    async def test_chat_stream_passes_formatted_session_context(self):
        fake_llm = FakeLLM()
        fake_goal_runtime = FakeGoalRuntime()
        fake_state = types.SimpleNamespace(
            llm=fake_llm,
            goal_runtime=fake_goal_runtime,
            agent=FakeAgent(),
            import_context=FakeImportContext(),
            privacy=FakePrivacy(),
        )
        fake_main = types.SimpleNamespace(app_state=fake_state)

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            response = await chat_stream(
                ChatRequest(message="继续解释一下", session_id="sess-chat")
            )
            async for _ in response.body_iterator:
                pass

        self.assertIn("第一轮问题", fake_llm.calls[0][2])

# tests/test_llm_streaming.py
    async def test_chat_stream_includes_session_context_system_message(self):
        service = LLMService("sk-demo", "https://api.example.com/v1", "demo-model")
        fake_client = FakeAsyncOpenAI(["你好", "，世界"])
        service.client = fake_client

        async for _ in service.chat_stream(
            "你好",
            gpu_context="GPU 状态: []",
            session_context="会话历史摘要：\n- 第一轮问题\n最近对话原文：\n第 1 轮\n用户：第一轮问题\n助手：第一轮回答",
        ):
            pass

        messages = fake_client.chat.completions.calls[0]["messages"]
        self.assertTrue(any("第一轮问题" in item["content"] for item in messages))
```

- [ ] **Step 2: Run the affected tests to verify they fail**

Run:

```bash
cmd.exe /d /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_ai_workbench_dispatch_api.py -q && .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_ai_chat_stream_api.py -q && .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_llm_streaming.py -q"
```

Expected: FAIL because `ChatRequest` / `AiWorkbenchDispatchRequest` do not accept `session_id` and AI routes/LLM service do not pass session context

- [ ] **Step 3: Implement the minimal chat/dispatch plumbing**

```python
# backend/app/models/schemas.py
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str = Field(default="", max_length=120)


class AiWorkbenchDispatchRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str = Field(default="", max_length=120)

# backend/app/services/llm.py
def _append_session_context_message(messages: list[dict], session_context: str) -> list[dict]:
    if session_context.strip():
        messages.append(
            {
                "role": "system",
                "content": f"当前会话记忆：\n{session_context}",
            }
        )
    return messages

async def chat(self, user_message: str, gpu_context: str = "", session_context: str = "") -> dict:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if gpu_context:
        messages.append({"role": "system", "content": f"当前GPU集群实时状态：\n{gpu_context}"})
    _append_session_context_message(messages, session_context)
    messages.append({"role": "user", "content": user_message})
    reply = await self._call_with_retry(
        model=self.model,
        messages=messages,
        temperature=0.7,
        max_tokens=2000,
    )
    return {
        "reply": reply,
        "suggestions": self._extract_suggestions(reply),
    }

async def chat_stream(self, user_message: str, gpu_context: str = "", session_context: str = ""):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if gpu_context:
        messages.append({"role": "system", "content": f"当前GPU集群实时状态：\n{gpu_context}"})
    _append_session_context_message(messages, session_context)
    messages.append({"role": "user", "content": user_message})
    async for item in self._stream_with_retry(
        model=self.model,
        messages=messages,
        temperature=0.7,
        max_tokens=2000,
    ):
        yield item

async def dispatch_workbench_message(self, user_message: str, gpu_context: str = "", session_context: str = "") -> dict:
    messages = [{"role": "system", "content": WORKBENCH_DISPATCH_PROMPT}]
    if gpu_context:
        messages.append({"role": "system", "content": f"当前GPU集群实时状态：\n{gpu_context}"})
    _append_session_context_message(messages, session_context)
    messages.append({"role": "user", "content": user_message})
    content = await self._call_with_retry(
        model=self.model,
        messages=messages,
        temperature=0.1,
        max_tokens=400,
    )
    parsed = self.parse_structured_json(content, label="AI 工作台判路结果")
    return _normalize_workbench_dispatch_result(parsed, user_message)

# backend/app/api/ai.py
from app.services.goal_runtime.session_context import format_session_context_for_prompt

async def _build_session_context_text(app_state, session_id: str, message: str) -> str:
    if not str(session_id or "").strip():
        return ""
    payload = await app_state.goal_runtime.build_session_context_payload(session_id, message)
    return format_session_context_for_prompt(payload)

@router.post("/chat")
async def chat(req: ChatRequest):
    llm = _require_llm(app_state)
    gpu_context = await _build_gpu_context(app_state)
    session_context = await _build_session_context_text(app_state, req.session_id, req.message)
    return await llm.chat(req.message, gpu_context, session_context)

@router.post("/workbench/dispatch")
async def dispatch_workbench_message(req: AiWorkbenchDispatchRequest):
    llm = _require_llm(app_state)
    gpu_context = await _build_gpu_context(app_state)
    session_context = await _build_session_context_text(app_state, req.session_id, req.message)
    return await llm.dispatch_workbench_message(req.message, gpu_context, session_context)

@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    llm = _require_llm(app_state)
    if not llm.supports_chat_stream():
        raise HTTPException(status_code=409, detail="当前模型不支持流式输出")
    gpu_context = await _build_gpu_context(app_state)
    session_context = await _build_session_context_text(app_state, req.session_id, req.message)

    async def iterator():
        full_text = ""
        yield encode_sse_event("start", {"message": req.message})
        async for delta in llm.chat_stream(req.message, gpu_context, session_context):
            full_text += delta
            yield encode_sse_event("delta", {"text": delta})
            yield encode_sse_event("snapshot", {"text": full_text})
        yield encode_sse_event(
            "completed",
            {
                "reply": full_text,
                "suggestions": LLMService._extract_suggestions(full_text),
            },
        )

    return StreamingResponse(iterator(), media_type="text/event-stream")
```

```javascript
// frontend/src/services/api.js
export const dispatchAiWorkbenchMessage = (message, session_id = '') =>
  api.post('/ai/workbench/dispatch', { message, session_id })

export const openAiChatStream = (message, session_id = '', options = {}) =>
  openAuthorizedEventStream('/api/ai/chat/stream', { message, session_id }, options)

// frontend/src/composables/useAiAssistantWorkbench.js
      const { data } = await dispatchAiWorkbenchMessage(text, previousSessionId)
      const response = await openAiChatStream(text, runtime.activeSessionId.value)
```

- [ ] **Step 4: Run the targeted tests and frontend build**

Run:

```bash
cmd.exe /d /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_ai_workbench_dispatch_api.py -q && .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_ai_chat_stream_api.py -q && .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_llm_streaming.py -q && cd frontend && npm run build"
```

Expected: all tests `OK`; Vite build exits `0`

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/schemas.py backend/app/api/ai.py backend/app/services/llm.py frontend/src/services/api.js frontend/src/composables/useAiAssistantWorkbench.js tests/test_ai_workbench_dispatch_api.py tests/test_ai_chat_stream_api.py tests/test_llm_streaming.py
git commit -m "feat: pass session memory through ai chat and dispatch"
```

### Task 4: Run The Focused Regression Suite

**Files:**
- Modify: `docs/superpowers/plans/2026-04-11-session-context-memory-implementation.md`

- [ ] **Step 1: Run the full focused regression suite**

Run:

```bash
cmd.exe /d /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_goal_runtime_session_context.py -q && .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_goal_runtime_api.py -q && .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_ai_workbench_dispatch_api.py -q && .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_ai_chat_stream_api.py -q && .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_llm_streaming.py -q && .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_frontend_ui_structure.py -q && .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_goal_runtime_capabilities.py -q && .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_import_layer_structure.py -q && cd frontend && npm run build"
```

Expected: all Python test commands report `OK`; frontend build exits `0`

- [ ] **Step 2: Confirm there is no hidden regression in runtime event persistence**

Run:

```bash
cmd.exe /d /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_goal_runtime_api.py -q"
```

Expected: the suite still reports `UserMessageSubmitted`, `AssistantMessageGenerated`, `LLMRequestPrepared`, `LLMResponseReceived`, and `LLMPlanExtracted` without losing `round_index`

- [ ] **Step 3: Update the implementation plan checklist with actual completion state**

```markdown
- [x] Task 1 complete
- [x] Task 2 complete
- [x] Task 3 complete
- [x] Task 4 complete
```

- [ ] **Step 4: Commit the completed implementation**

```bash
git add backend/app/services/goal_runtime/session_context.py backend/app/services/goal_runtime/service.py backend/app/services/goal_runtime/session_runtime.py backend/app/services/goal_runtime/reasoning_trace.py backend/app/services/llm.py backend/app/api/ai.py backend/app/models/schemas.py frontend/src/services/api.js frontend/src/composables/useAiAssistantWorkbench.js tests/test_goal_runtime_session_context.py tests/test_goal_runtime_api.py tests/test_ai_workbench_dispatch_api.py tests/test_ai_chat_stream_api.py tests/test_llm_streaming.py docs/superpowers/plans/2026-04-11-session-context-memory-implementation.md
git commit -m "feat: add session memory to ai workbench and runtime"
```

## Self-Review

- Spec coverage:
  - “最近原文 + 更早摘要 + runtime 摘要”由 Task 1 实现。
  - “runtime planning 注入 session context”由 Task 2 实现。
  - “chat / dispatch 注入 session context + 前端继续传 session_id”由 Task 3 实现。
  - “压缩后仍超预算显式报错”由 Task 1 测试和实现覆盖。
  - “回归验证”由 Task 4 覆盖。
- Placeholder scan:
  - 已检查并移除占位式任务描述、未完成标记和跨任务引用写法。
- Type consistency:
  - 新增请求字段统一使用 `session_id: str = Field(default="", max_length=120)`。
  - `LLMService` 三个入口统一接收 `session_context: str = ""`。
  - `GoalRuntimeService.build_session_context_payload()` 统一返回上下文字典，`format_session_context_for_prompt()` 负责字符串格式化。
