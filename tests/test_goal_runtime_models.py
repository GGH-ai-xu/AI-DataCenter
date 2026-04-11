import os
import sys

import pytest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.models.schemas import (  # noqa: E402
    AgentRuntimeApprovalRequest,
    AgentRuntimeChatTurnRequest,
    AgentRuntimeSessionResponse,
    AgentRuntimeStartRequest,
)
from app.services.goal_runtime.capability import CapabilityDefinition  # noqa: E402
from app.services.goal_runtime.execution_plan import ExecutionPlan, PlanStep  # noqa: E402
from app.services.goal_runtime.goal_spec import GoalSpec, normalize_permission_mode  # noqa: E402
from app.services.goal_runtime.session_events import build_goal_parsed_event  # noqa: E402


def test_goal_spec_normalizes_permission_mode_and_scope():
    spec = GoalSpec(
        session_id="sess-1",
        raw_message="把总功率压到 1200W 以下",
        goal_type="runtime_control",
        permission_mode="HIGH",
        scope_gpu_indexes=(3, 1, 3),
        constraints=("不影响 urgent 任务",),
        done_when="current_total_power <= 1200",
        abort_when=("no_capability_path",),
    )

    assert normalize_permission_mode("HIGH") == "high"
    assert normalize_permission_mode(None) == "low"
    assert spec.permission_mode == "high"
    assert spec.scope_gpu_indexes == (1, 3)


def test_execution_plan_tracks_steps_and_replan_budget():
    step = PlanStep(
        step_id="step-read",
        capability_name="runtime.snapshot.read",
        arguments={},
        approval_required=False,
    )
    plan = ExecutionPlan(plan_id="plan-1", steps=(step,), replan_budget=3)

    assert plan.remaining_step_ids() == ("step-read",)
    assert plan.can_replan() is True


def test_capability_definition_exposes_side_effect_layer():
    definition = CapabilityDefinition(
        name="tasks.pause",
        domain="tasks",
        side_effect_level="runtime_action",
        requires_scope=True,
        supported_providers=("http_local", "ssh_linux"),
    )

    assert definition.side_effect_level == "runtime_action"
    assert definition.requires_scope is True


def test_goal_parsed_event_payload_contains_summary_fields():
    event = build_goal_parsed_event(
        session_id="sess-1",
        goal_type="runtime_control",
        permission_mode="low",
        summary="降低总功率且不影响 urgent 任务",
    )

    assert event.event_type == "GoalParsed"
    assert event.payload["permission_mode"] == "low"
    assert event.payload["summary"] == "降低总功率且不影响 urgent 任务"


def test_agent_runtime_request_and_response_schemas_expose_session_fields():
    request = AgentRuntimeStartRequest(message="分析当前集群", session_id="sess-1")
    chat_turn = AgentRuntimeChatTurnRequest(
        message="你能查看当前任务吗",
        reply="可以，我能查看当前导入范围内的 GPU 进程。",
        permission_mode="low",
        session_id="sess-1",
        reply_mode="inline",
        suggestions=["查看当前任务列表"],
    )
    approval = AgentRuntimeApprovalRequest(approved=True)
    response = AgentRuntimeSessionResponse(
        session_id="sess-1",
        status="running",
        permission_mode="low",
    )

    assert request.permission_mode == "low"
    assert request.session_id == "sess-1"
    assert chat_turn.session_id == "sess-1"
    assert chat_turn.reply_mode == "inline"
    assert chat_turn.suggestions == ["查看当前任务列表"]
    assert approval.approved is True
    assert response.requires_approval is False
