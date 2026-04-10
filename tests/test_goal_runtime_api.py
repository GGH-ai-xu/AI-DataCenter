import asyncio
import os
import sys
import types
import unittest
from unittest import mock


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.api.agent_runtime import (  # noqa: E402
    approve_agent_runtime_session,
    delete_agent_runtime_session,
    get_agent_runtime_events,
    get_agent_runtime_session,
    list_agent_runtime_sessions,
    start_agent_runtime_session,
    stream_agent_runtime_session,
)
from app.models.schemas import (  # noqa: E402
    AgentRuntimeApprovalRequest,
    AgentRuntimeStartRequest,
)
from app.services.goal_runtime.capability import CapabilityDefinition  # noqa: E402
from app.services.goal_runtime.capability_registry import CapabilityRegistry  # noqa: E402
from app.services.goal_runtime.service import GoalRuntimeService  # noqa: E402


class FakeImportContext:
    def selected_gpu_indexes(self):
        return [0]


class FakeStore:
    def __init__(self):
        self.sessions = {}
        self.events = {}
        self.stream_states = {}

    async def create_agent_session(
        self,
        session_id,
        goal_json,
        permission_mode,
        status,
        summary,
    ):
        self.sessions[session_id] = {
            "session_id": session_id,
            "goal_json": dict(goal_json),
            "permission_mode": permission_mode,
            "status": status,
            "live_phase": "planning",
            "summary": summary,
        }

    async def update_agent_session_status(
        self,
        session_id,
        status,
        summary="",
        live_phase=None,
    ):
        self.sessions[session_id]["status"] = status
        self.sessions[session_id]["summary"] = summary
        if live_phase is not None:
            self.sessions[session_id]["live_phase"] = live_phase

    async def append_agent_event(self, session_id, event_type, payload, **metadata):
        self.events.setdefault(session_id, []).append(
            {
                "session_id": session_id,
                "event_type": event_type,
                "payload": dict(payload),
                **metadata,
            }
        )

    async def get_agent_session(self, session_id):
        return self.sessions.get(session_id)

    async def get_agent_events(self, session_id):
        return list(self.events.get(session_id, []))

    async def upsert_agent_stream_state(
        self,
        session_id,
        stream_kind,
        *,
        latest_text,
        latest_char_count,
        revision,
    ):
        self.stream_states[(session_id, stream_kind)] = {
            "session_id": session_id,
            "stream_kind": stream_kind,
            "latest_text": latest_text,
            "latest_char_count": latest_char_count,
            "revision": revision,
        }

    async def get_agent_stream_state(self, session_id, stream_kind):
        return self.stream_states.get((session_id, stream_kind))

    async def delete_agent_session(self, session_id):
        self.sessions.pop(session_id, None)
        self.events.pop(session_id, None)
        for key in [key for key in self.stream_states if key[0] == session_id]:
            self.stream_states.pop(key, None)


def build_registry():
    registry = CapabilityRegistry()

    async def read_snapshot(_context, _arguments):
        return {"gpus": [{"index": 0}], "processes": []}

    async def set_power_limit(_context, arguments):
        return {"success": True, "gpu_index": arguments["gpu_index"]}

    registry.register(
        CapabilityDefinition(
            "runtime.snapshot.read",
            "runtime",
            "observe",
            False,
            ("http_local",),
        ),
        handler=read_snapshot,
    )
    registry.register(
        CapabilityDefinition(
            "scheduler.power_limit.set",
            "scheduler",
            "runtime_action",
            True,
            ("http_local",),
        ),
        handler=set_power_limit,
    )
    return registry


class FakeLLM:
    def __init__(self, plan):
        self.plan = plan
        self.calls = []

    async def generate_control_plan(self, user_message, control_context):
        self.calls.append((user_message, control_context))
        return dict(self.plan)


class FakeGoalRuntimeService:
    def __init__(self):
        self.calls = []

    async def start_session(self, message, permission_mode):
        self.calls.append(("start", message, permission_mode))
        return {
            "session_id": "sess-route",
            "status": "running",
            "live_phase": "planning",
        }

    async def resolve_approval(self, session_id, approved):
        self.calls.append(("approve", session_id, approved))
        return {"session_id": session_id, "status": "completed" if approved else "aborted"}

    async def get_session(self, session_id):
        self.calls.append(("session", session_id))
        return {
            "session_id": session_id,
            "status": "completed",
            "live_phase": "completed",
            "event_count": 1,
            "current_round": 1,
            "llm_call_count": 0,
            "awaiting_approval": False,
            "pending_approval": None,
            "latest_error": "",
            "planner_stream": None,
        }

    async def get_events(self, session_id):
        self.calls.append(("events", session_id))
        return [{"event_type": "GoalParsed"}]

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

    async def delete_session(self, session_id):
        self.calls.append(("delete", session_id))
        return {"session_id": session_id, "deleted": True}

    async def stream_session(self, session_id):
        self.calls.append(("stream", session_id))
        yield {"event": "session_started", "data": {"session_id": session_id}}
        yield {
            "event": "planner_snapshot",
            "data": {"latest_text": "正在生成计划", "revision": 1},
        }
        yield {
            "event": "completed",
            "data": {"session_id": session_id, "status": "awaiting_approval"},
        }


class GoalRuntimeServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_session_emits_llm_trace_events_when_llm_available(self):
        store = FakeStore()
        runtime = GoalRuntimeService(
            store=store,
            registry=build_registry(),
            import_context=FakeImportContext(),
            runtime_status_reader=None,
            llm_service_reader=lambda: FakeLLM(
                {
                    "summary": "计划限制 GPU 0 功耗并等待审批",
                    "risk_level": "medium",
                    "requires_confirmation": True,
                    "warnings": [],
                    "actions": [
                        {
                            "action": "set_power_limit",
                            "target": {"gpu_index": 0, "power_limit": 220},
                            "reason": "削峰",
                        }
                    ],
                }
            ),
            task_spawner=lambda coro: asyncio.create_task(coro),
        )

        result = await runtime.start_session(
            "把 GPU 0 的功耗上限调到 220W",
            "low",
        )
        await runtime.wait_for_idle()
        events = await runtime.get_events(result["session_id"])
        event_types = [item["event_type"] for item in events]

        self.assertEqual(result["status"], "running")
        self.assertEqual(result["live_phase"], "planning")
        self.assertIn("ContextSnapshotCaptured", event_types)
        self.assertIn("LLMRequestPrepared", event_types)
        self.assertIn("LLMResponseReceived", event_types)
        self.assertIn("LLMPlanExtracted", event_types)

    async def test_start_session_emits_explicit_rule_fallback_when_llm_unavailable(self):
        store = FakeStore()
        runtime = GoalRuntimeService(
            store=store,
            registry=build_registry(),
            import_context=FakeImportContext(),
            runtime_status_reader=None,
            llm_service_reader=lambda: None,
            task_spawner=lambda coro: asyncio.create_task(coro),
        )

        result = await runtime.start_session(
            "执行一次调度",
            "high",
        )
        await runtime.wait_for_idle()
        events = await runtime.get_events(result["session_id"])
        event_types = [item["event_type"] for item in events]

        self.assertIn("LLMUnavailable", event_types)
        self.assertIn("RuleFallbackUsed", event_types)

    async def test_start_session_returns_running_planning_before_background_finishes(self):
        class SlowStreamingLLM:
            def supports_control_plan_stream(self):
                return True

            async def generate_control_plan_stream(self, _message, _context):
                yield '{"summary":"执行一次调度","risk_level":"low",'
                await asyncio.sleep(0)
                yield '"requires_confirmation":false,"warnings":[],"actions":[]}'

        store = FakeStore()
        runtime = GoalRuntimeService(
            store=store,
            registry=build_registry(),
            import_context=FakeImportContext(),
            runtime_status_reader=None,
            llm_service_reader=lambda: SlowStreamingLLM(),
            task_spawner=lambda coro: asyncio.create_task(coro),
        )

        result = await runtime.start_session(
            "执行一次调度",
            "low",
        )
        self.assertEqual(result["status"], "running")
        self.assertEqual(result["live_phase"], "planning")
        await runtime.wait_for_idle()

        session = await runtime.get_session(result["session_id"])
        self.assertIn("live_phase", session)
        self.assertIn("planner_stream", session)

    async def test_start_session_persists_original_message_in_goal_json_raw_message(self):
        store = FakeStore()
        runtime = GoalRuntimeService(
            store=store,
            registry=build_registry(),
            import_context=FakeImportContext(),
            runtime_status_reader=None,
            llm_service_reader=lambda: None,
            task_spawner=lambda coro: asyncio.create_task(coro),
        )

        result = await runtime.start_session(
            "把 GPU 0 的功耗上限调到 220W",
            "low",
        )

        self.assertEqual(
            store.sessions[result["session_id"]]["goal_json"]["raw_message"],
            "把 GPU 0 的功耗上限调到 220W",
        )

    async def test_start_session_accepts_code_fenced_streamed_control_plan(self):
        class CodeFencedStreamingLLM:
            def supports_control_plan_stream(self):
                return True

            async def generate_control_plan_stream(self, _message, _context):
                yield "```json\n"
                yield '{"summary":"把 GPU 0 的功耗上限调到 220W","risk_level":"medium",'
                yield '"requires_confirmation":true,"warnings":[],"actions":[{"action":"set_power_limit","target":{"gpu_index":0,"power_limit":220},"reason":"削峰"}]}'
                yield "\n```"

        store = FakeStore()
        runtime = GoalRuntimeService(
            store=store,
            registry=build_registry(),
            import_context=FakeImportContext(),
            runtime_status_reader=None,
            llm_service_reader=lambda: CodeFencedStreamingLLM(),
            task_spawner=lambda coro: asyncio.create_task(coro),
        )

        result = await runtime.start_session(
            "把 GPU 0 的功耗上限调到 220W",
            "low",
        )
        await runtime.wait_for_idle()
        events = await runtime.get_events(result["session_id"])
        event_types = [item["event_type"] for item in events]

        self.assertIn("LLMRequestPrepared", event_types)
        self.assertIn("LLMResponseReceived", event_types)
        self.assertNotIn("LLMCallFailed", event_types)

    async def test_start_session_records_friendly_llm_parse_failure_and_attempt_count(self):
        class InvalidStreamingLLM:
            def supports_control_plan_stream(self):
                return True

            async def generate_control_plan_stream(self, _message, _context):
                yield "先分析一下当前情况。"

        store = FakeStore()
        runtime = GoalRuntimeService(
            store=store,
            registry=build_registry(),
            import_context=FakeImportContext(),
            runtime_status_reader=None,
            llm_service_reader=lambda: InvalidStreamingLLM(),
            task_spawner=lambda coro: asyncio.create_task(coro),
        )

        result = await runtime.start_session(
            "把 GPU 0 的功耗上限调到 220W",
            "low",
        )
        await runtime.wait_for_idle()

        session = await runtime.get_session(result["session_id"])
        events = await runtime.get_events(result["session_id"])
        failure_event = next(
            item for item in events
            if item["event_type"] == "LLMCallFailed"
        )

        self.assertEqual(session["llm_call_count"], 1)
        self.assertEqual(session["status"], "awaiting_approval")
        self.assertIn("合法 JSON", failure_event["payload"]["error"])

    async def test_start_session_reaches_awaiting_approval_after_background_run(self):
        store = FakeStore()
        runtime = GoalRuntimeService(
            store=store,
            registry=build_registry(),
            import_context=FakeImportContext(),
            runtime_status_reader=None,
            llm_service_reader=lambda: None,
            task_spawner=lambda coro: asyncio.create_task(coro),
        )

        result = await runtime.start_session(
            "把 GPU 0 的功耗上限调到 220W",
            "low",
        )
        await runtime.wait_for_idle()

        session = await runtime.get_session(result["session_id"])
        self.assertEqual(session["status"], "awaiting_approval")
        self.assertIn("event_count", session)
        self.assertIn("current_round", session)
        self.assertIn("llm_call_count", session)
        self.assertIn("awaiting_approval", session)
        self.assertIn("pending_approval", session)
        self.assertIn("planner_stream", session)
        self.assertGreaterEqual(len(await runtime.get_events(result["session_id"])), 2)

    async def test_resolve_approval_completes_pending_runtime_action(self):
        store = FakeStore()
        runtime = GoalRuntimeService(
            store=store,
            registry=build_registry(),
            import_context=FakeImportContext(),
            runtime_status_reader=None,
            llm_service_reader=lambda: None,
            task_spawner=lambda coro: asyncio.create_task(coro),
        )
        started = await runtime.start_session(
            "把 GPU 0 的功耗上限调到 220W",
            "low",
        )
        await runtime.wait_for_idle()

        resolved = await runtime.resolve_approval(started["session_id"], True)

        self.assertEqual(resolved["status"], "completed")
        self.assertEqual(store.sessions[started["session_id"]]["status"], "completed")

    async def test_delete_session_removes_completed_session(self):
        store = FakeStore()
        runtime = GoalRuntimeService(
            store=store,
            registry=build_registry(),
            import_context=FakeImportContext(),
            runtime_status_reader=None,
            llm_service_reader=lambda: None,
            task_spawner=lambda coro: asyncio.create_task(coro),
        )
        await store.create_agent_session(
            "sess-completed",
            {"message": "删除已完成会话"},
            "low",
            "completed",
            "删除已完成会话",
        )
        await store.append_agent_event(
            "sess-completed",
            "SessionCompleted",
            {"summary": "完成"},
        )
        await store.upsert_agent_stream_state(
            "sess-completed",
            "planner",
            latest_text="最终计划",
            latest_char_count=4,
            revision=1,
        )

        result = await runtime.delete_session("sess-completed")

        self.assertEqual(result["session_id"], "sess-completed")
        self.assertTrue(result["deleted"])
        self.assertNotIn("sess-completed", store.sessions)
        self.assertEqual(store.events.get("sess-completed"), None)

    async def test_delete_session_rejects_running_session(self):
        store = FakeStore()
        runtime = GoalRuntimeService(
            store=store,
            registry=build_registry(),
            import_context=FakeImportContext(),
            runtime_status_reader=None,
            llm_service_reader=lambda: None,
            task_spawner=lambda coro: asyncio.create_task(coro),
        )
        await store.create_agent_session(
            "sess-running",
            {"message": "删除运行中会话"},
            "low",
            "running",
            "删除运行中会话",
        )

        with self.assertRaises(RuntimeError):
            await runtime.delete_session("sess-running")


class GoalRuntimeRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_routes_delegate_to_goal_runtime_service(self):
        fake_runtime = FakeGoalRuntimeService()
        fake_main = types.SimpleNamespace(app_state=types.SimpleNamespace(goal_runtime=fake_runtime))

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            started = await start_agent_runtime_session(
                AgentRuntimeStartRequest(
                    message="暂停当前低优先级任务",
                    permission_mode="low",
                )
            )
            approved = await approve_agent_runtime_session(
                "sess-route",
                AgentRuntimeApprovalRequest(approved=True),
            )
            session = await get_agent_runtime_session("sess-route")
            events = await get_agent_runtime_events("sess-route")

        self.assertEqual(started["status"], "running")
        self.assertEqual(started["live_phase"], "planning")
        self.assertEqual(approved["status"], "completed")
        self.assertEqual(session["status"], "completed")
        self.assertIn("event_count", session)
        self.assertIn("awaiting_approval", session)
        self.assertEqual(events["events"][0]["event_type"], "GoalParsed")

    async def test_stream_route_delegates_to_goal_runtime_service(self):
        fake_runtime = FakeGoalRuntimeService()
        fake_main = types.SimpleNamespace(app_state=types.SimpleNamespace(goal_runtime=fake_runtime))

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            response = await stream_agent_runtime_session("sess-route")
            chunks = []
            async for item in response.body_iterator:
                chunks.append(item.decode("utf-8"))

        payload = "".join(chunks)
        self.assertIn("event: planner_snapshot", payload)
        self.assertIn('"latest_text": "正在生成计划"', payload)

    async def test_list_sessions_route_delegates_to_goal_runtime_service(self):
        fake_runtime = FakeGoalRuntimeService()
        fake_main = types.SimpleNamespace(
            app_state=types.SimpleNamespace(goal_runtime=fake_runtime)
        )

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            payload = await list_agent_runtime_sessions(limit=20)

        self.assertEqual(payload["sessions"][0]["session_id"], "sess-route")
        self.assertIn(("list", 20), fake_runtime.calls)

    async def test_delete_session_route_delegates_to_goal_runtime_service(self):
        fake_runtime = FakeGoalRuntimeService()
        fake_main = types.SimpleNamespace(
            app_state=types.SimpleNamespace(goal_runtime=fake_runtime)
        )

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            payload = await delete_agent_runtime_session("sess-route")

        self.assertTrue(payload["deleted"])
        self.assertIn(("delete", "sess-route"), fake_runtime.calls)


if __name__ == "__main__":
    unittest.main()
