import os
import sys
import types
import unittest
from unittest import mock


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.api.agent_runtime import (  # noqa: E402
    approve_agent_runtime_session,
    get_agent_runtime_events,
    get_agent_runtime_session,
    start_agent_runtime_session,
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
            "summary": summary,
        }

    async def update_agent_session_status(self, session_id, status, summary=""):
        self.sessions[session_id]["status"] = status
        self.sessions[session_id]["summary"] = summary

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
        return {"session_id": "sess-route", "status": "awaiting_approval"}

    async def resolve_approval(self, session_id, approved):
        self.calls.append(("approve", session_id, approved))
        return {"session_id": session_id, "status": "completed" if approved else "aborted"}

    async def get_session(self, session_id):
        self.calls.append(("session", session_id))
        return {"session_id": session_id, "status": "completed"}

    async def get_events(self, session_id):
        self.calls.append(("events", session_id))
        return [{"event_type": "GoalParsed"}]


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
        )

        result = await runtime.start_session(
            "把 GPU 0 的功耗上限调到 220W",
            "low",
        )
        events = await runtime.get_events(result["session_id"])
        event_types = [item["event_type"] for item in events]

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
        )

        result = await runtime.start_session(
            "执行一次调度",
            "high",
        )
        events = await runtime.get_events(result["session_id"])
        event_types = [item["event_type"] for item in events]

        self.assertIn("LLMUnavailable", event_types)
        self.assertIn("RuleFallbackUsed", event_types)

    async def test_start_session_persists_and_returns_awaiting_approval_for_low_mode(self):
        store = FakeStore()
        runtime = GoalRuntimeService(
            store=store,
            registry=build_registry(),
            import_context=FakeImportContext(),
            runtime_status_reader=None,
            llm_service_reader=lambda: None,
        )

        result = await runtime.start_session(
            "把 GPU 0 的功耗上限调到 220W",
            "low",
        )

        self.assertEqual(result["status"], "awaiting_approval")
        session = await runtime.get_session(result["session_id"])
        self.assertEqual(session["status"], "awaiting_approval")
        self.assertGreaterEqual(len(await runtime.get_events(result["session_id"])), 2)

    async def test_resolve_approval_completes_pending_runtime_action(self):
        store = FakeStore()
        runtime = GoalRuntimeService(
            store=store,
            registry=build_registry(),
            import_context=FakeImportContext(),
            runtime_status_reader=None,
            llm_service_reader=lambda: None,
        )
        started = await runtime.start_session(
            "把 GPU 0 的功耗上限调到 220W",
            "low",
        )

        resolved = await runtime.resolve_approval(started["session_id"], True)

        self.assertEqual(resolved["status"], "completed")
        self.assertEqual(store.sessions[started["session_id"]]["status"], "completed")


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

        self.assertEqual(started["status"], "awaiting_approval")
        self.assertEqual(approved["status"], "completed")
        self.assertEqual(session["status"], "completed")
        self.assertEqual(events["events"][0]["event_type"], "GoalParsed")


if __name__ == "__main__":
    unittest.main()
