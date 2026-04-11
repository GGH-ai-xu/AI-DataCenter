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

    async def dispatch_workbench_message(self, message, gpu_context="", session_context=None):
        self.calls.append((message, gpu_context, session_context))
        if self.error:
            raise self.error
        return dict(self.result)


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
            goal_runtime=FakeGoalRuntime(),
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
            goal_runtime=FakeGoalRuntime(),
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
            goal_runtime=FakeGoalRuntime(),
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
            goal_runtime=FakeGoalRuntime(),
        )
        fake_main = types.SimpleNamespace(app_state=fake_state)

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            with self.assertRaises(HTTPException) as ctx:
                await dispatch_workbench_message(
                    AiWorkbenchDispatchRequest(message="帮我处理一下")
                )

        self.assertEqual(ctx.exception.status_code, 502)

    async def test_dispatch_passes_session_context_when_session_id_present(self):
        fake_llm = FakeLLM({"route_kind": "chat", "reply_mode": "stream"})
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
            await dispatch_workbench_message(
                AiWorkbenchDispatchRequest(
                    message="继续刚才那个任务",
                    session_id="sess-workbench",
                )
            )

        self.assertEqual(
            fake_runtime.calls,
            [("sess-workbench", "继续刚才那个任务")],
        )
        self.assertEqual(
            fake_llm.calls[0][2]["session_id"],
            "sess-workbench",
        )


if __name__ == "__main__":
    unittest.main()
