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
from app.services.llm import LLMService  # noqa: E402


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
    def test_llm_service_exposes_dispatch_workbench_message(self):
        self.assertTrue(hasattr(LLMService, "dispatch_workbench_message"))

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


if __name__ == "__main__":
    unittest.main()
