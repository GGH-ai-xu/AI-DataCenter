import os
import sys
import types
import unittest
from unittest import mock


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.api.ai import chat, chat_stream  # noqa: E402
from app.models.schemas import ChatRequest  # noqa: E402


class FakeLLM:
    def __init__(self):
        self.chat_calls = []
        self.stream_calls = []

    def supports_chat_stream(self):
        return True

    async def chat(self, message, gpu_context="", session_context=None):
        self.chat_calls.append((message, gpu_context, session_context))
        return {"reply": "你好，世界", "suggestions": []}

    async def chat_stream(self, message, gpu_context="", session_context=None):
        self.stream_calls.append((message, gpu_context, session_context))
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
                    "messages": [{"role": "user", "content": "上一轮问题"}],
                }
            ],
            "historical_summary": {"round_count": 0, "summary_lines": [], "entities": {}, "constraints": []},
            "runtime_summary": {
                "latest_plan": "",
                "approval_status": "",
                "latest_execution": "",
                "latest_failure": "",
                "live_phase": "completed",
            },
        }


class AIChatStreamRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_stream_returns_sse_frames(self):
        fake_llm = FakeLLM()
        fake_state = types.SimpleNamespace(
            llm=fake_llm,
            agent=FakeAgent(),
            import_context=FakeImportContext(),
            privacy=FakePrivacy(),
            goal_runtime=FakeGoalRuntime(),
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

    async def test_chat_route_passes_session_context_when_session_id_present(self):
        fake_llm = FakeLLM()
        fake_runtime = FakeGoalRuntime()
        fake_state = types.SimpleNamespace(
            llm=fake_llm,
            agent=FakeAgent(),
            import_context=FakeImportContext(),
            privacy=FakePrivacy(),
            goal_runtime=fake_runtime,
        )
        fake_main = types.SimpleNamespace(app_state=fake_state)

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            response = await chat(ChatRequest(message="继续刚才那个任务", session_id="sess-chat"))

        self.assertEqual(response["reply"], "你好，世界")
        self.assertEqual(fake_runtime.calls, [("sess-chat", "继续刚才那个任务")])
        self.assertEqual(fake_llm.chat_calls[0][2]["session_id"], "sess-chat")

    async def test_chat_stream_passes_session_context_when_session_id_present(self):
        fake_llm = FakeLLM()
        fake_runtime = FakeGoalRuntime()
        fake_state = types.SimpleNamespace(
            llm=fake_llm,
            agent=FakeAgent(),
            import_context=FakeImportContext(),
            privacy=FakePrivacy(),
            goal_runtime=fake_runtime,
        )
        fake_main = types.SimpleNamespace(app_state=fake_state)

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            response = await chat_stream(
                ChatRequest(message="继续刚才那个任务", session_id="sess-stream")
            )
            async for _ in response.body_iterator:
                pass

        self.assertEqual(fake_runtime.calls, [("sess-stream", "继续刚才那个任务")])
        self.assertEqual(fake_llm.stream_calls[0][2]["session_id"], "sess-stream")


if __name__ == "__main__":
    unittest.main()
