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

    async def test_chat_stream_includes_session_context_as_system_message(self):
        service = LLMService("sk-demo", "https://api.example.com/v1", "demo-model")
        service.client = FakeAsyncOpenAI(["你好"])
        session_context = {
            "session_id": "sess-1",
            "current_request": {"message": "继续刚才那个任务"},
            "recent_messages": [
                {
                    "round_index": 1,
                    "messages": [{"role": "user", "content": "第一轮问题"}],
                }
            ],
            "historical_summary": {
                "round_count": 0,
                "summary_lines": [],
                "entities": {},
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

        async for _ in service.chat_stream(
            "继续刚才那个任务",
            "GPU状态: []",
            session_context,
        ):
            pass

        messages = service.client.chat.completions.calls[0]["messages"]
        self.assertTrue(
            any("会话历史摘要：" in item["content"] for item in messages),
        )

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


if __name__ == "__main__":
    unittest.main()
