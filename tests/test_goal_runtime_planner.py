import asyncio
import os
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.goal_runtime.capability import CapabilityDefinition  # noqa: E402
from app.services.goal_runtime.capability_registry import CapabilityRegistry  # noqa: E402
from app.services.goal_runtime.goal_parser import parse_goal_message  # noqa: E402
from app.services.goal_runtime.goal_spec import GoalSpec  # noqa: E402
from app.services.goal_runtime.planner import build_initial_plan  # noqa: E402


class FakeImportContext:
    def __init__(self, gpu_indexes):
        self._gpu_indexes = gpu_indexes

    def selected_gpu_indexes(self):
        return list(self._gpu_indexes)


def build_test_registry():
    registry = CapabilityRegistry()
    registry.register(
        CapabilityDefinition(
            "runtime.snapshot.read",
            "runtime",
            "observe",
            False,
            ("http_local",),
        ),
        handler=lambda ctx, args: None,
    )
    registry.register(
        CapabilityDefinition(
            "scheduler.power_limit.set",
            "scheduler",
            "runtime_action",
            True,
            ("http_local",),
        ),
        handler=lambda ctx, args: None,
    )
    registry.register(
        CapabilityDefinition(
            "tasks.pause",
            "tasks",
            "runtime_action",
            True,
            ("http_local",),
        ),
        handler=lambda ctx, args: None,
    )
    return registry


def test_parse_goal_message_extracts_runtime_control_constraints():
    spec = asyncio.run(
        parse_goal_message(
            session_id="sess-1",
            message="把 GPU 0 的功耗上限调到 220W，但不要影响 urgent 任务",
            permission_mode="high",
            import_context=FakeImportContext([0, 1]),
            llm_service=None,
        )
    )

    assert spec.goal_type == "runtime_control"
    assert "urgent" in " ".join(spec.constraints)
    assert spec.scope_gpu_indexes == (0, 1)


def test_build_initial_plan_prefers_read_then_runtime_actions():
    plan = build_initial_plan(
        goal_spec=GoalSpec(
            session_id="sess-1",
            raw_message="把 GPU 0 的功耗上限调到 220W",
            goal_type="runtime_control",
            permission_mode="low",
            scope_gpu_indexes=(0,),
            constraints=(),
            done_when="goal_constraints_satisfied",
            abort_when=("no_capability_path",),
        ),
        registry=build_test_registry(),
    )

    assert plan.steps[0].capability_name == "runtime.snapshot.read"
    assert plan.steps[-1].capability_name == "scheduler.power_limit.set"
    assert plan.steps[-1].fallback_capabilities == ("tasks.pause",)
