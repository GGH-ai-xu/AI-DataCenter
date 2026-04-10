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


if __name__ == "__main__":
    unittest.main()
