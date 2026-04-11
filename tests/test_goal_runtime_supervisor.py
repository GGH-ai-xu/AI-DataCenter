import os
import sys
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.goal_runtime.capability import CapabilityDefinition  # noqa: E402
from app.services.goal_runtime.capability_registry import CapabilityRegistry  # noqa: E402
from app.services.goal_runtime.execution_plan import ExecutionPlan, PlanStep  # noqa: E402
from app.services.goal_runtime.goal_spec import GoalSpec  # noqa: E402
from app.services.goal_runtime.supervisor import execute_plan_session  # noqa: E402


class FakePersistence:
    def __init__(self):
        self.events = []

    async def append_event(self, session_id, event_type, payload, **metadata):
        self.events.append(
            {
                "session_id": session_id,
                "event_type": event_type,
                "payload": payload,
                "round_index": int(metadata.get("round_index") or 0),
                "sequence": int(metadata.get("sequence") or 0),
            }
        )


def build_registry(
    primary_handler,
    fallback_handler,
):
    registry = CapabilityRegistry()
    registry.register(
        CapabilityDefinition(
            "runtime.snapshot.read",
            "runtime",
            "observe",
            False,
            ("http_local",),
        ),
        handler=primary_handler,
    )
    registry.register(
        CapabilityDefinition(
            "scheduler.power_limit.set",
            "scheduler",
            "runtime_action",
            True,
            ("http_local",),
        ),
        handler=primary_handler,
    )
    registry.register(
        CapabilityDefinition(
            "tasks.pause",
            "tasks",
            "runtime_action",
            True,
            ("http_local",),
        ),
        handler=fallback_handler,
    )
    return registry


class GoalRuntimeSupervisorTests(unittest.IsolatedAsyncioTestCase):
    async def test_high_permission_reroutes_to_fallback_without_approval(self):
        async def failing_primary(_context, _arguments):
            return {"success": False, "error": "primary failed"}

        async def working_fallback(_context, _arguments):
            return {"success": True, "action": "paused"}

        persistence = FakePersistence()
        result = await execute_plan_session(
            session_id="sess-1",
            goal_spec=GoalSpec(
                session_id="sess-1",
                raw_message="压低功耗",
                goal_type="runtime_control",
                permission_mode="high",
                scope_gpu_indexes=(0,),
                constraints=(),
                done_when="goal_constraints_satisfied",
                abort_when=("no_capability_path",),
            ),
            plan=ExecutionPlan(
                plan_id="plan-1",
                steps=(
                    PlanStep(
                        step_id="step-power",
                        capability_name="scheduler.power_limit.set",
                        arguments={"gpu_index": 0, "power_limit": 220},
                        approval_required=False,
                        fallback_capabilities=("tasks.pause",),
                    ),
                ),
            ),
            registry=build_registry(failing_primary, working_fallback),
            persistence=persistence,
        )

        self.assertEqual(result["status"], "completed")
        self.assertIn("PlanRevised", result["event_types"])
        self.assertEqual(persistence.events[0]["round_index"], 1)
        self.assertEqual(persistence.events[0]["sequence"], 1)

    async def test_low_permission_blocks_when_react_introduces_runtime_action(self):
        async def failing_primary(_context, _arguments):
            return {"success": False, "error": "need runtime action"}

        async def working_fallback(_context, _arguments):
            return {"success": True, "action": "paused"}

        persistence = FakePersistence()
        result = await execute_plan_session(
            session_id="sess-2",
            goal_spec=GoalSpec(
                session_id="sess-2",
                raw_message="处理当前负载",
                goal_type="runtime_control",
                permission_mode="low",
                scope_gpu_indexes=(0,),
                constraints=(),
                done_when="goal_constraints_satisfied",
                abort_when=("no_capability_path",),
            ),
            plan=ExecutionPlan(
                plan_id="plan-2",
                steps=(
                    PlanStep(
                        step_id="step-read",
                        capability_name="runtime.snapshot.read",
                        arguments={},
                        approval_required=False,
                        fallback_capabilities=("tasks.pause",),
                    ),
                ),
            ),
            registry=build_registry(failing_primary, working_fallback),
            persistence=persistence,
        )

        self.assertEqual(result["status"], "awaiting_approval")
        self.assertEqual(
            result["pending_approval"]["actions"][0]["capability_name"],
            "tasks.pause",
        )
        self.assertEqual(
            [item["sequence"] for item in persistence.events],
            list(range(1, len(persistence.events) + 1)),
        )


if __name__ == "__main__":
    unittest.main()
