from __future__ import annotations

from app.services.goal_runtime.control_heuristics import build_control_heuristic
from app.services.goal_runtime.execution_plan import ExecutionPlan, PlanStep
from app.services.goal_runtime.permission_policy import requires_approval


ACTION_CAPABILITY_MAP = {
    "set_power_limit": "scheduler.power_limit.set",
    "pause_task": "tasks.pause",
    "resume_task": "tasks.resume",
    "terminate_task": "tasks.terminate",
    "set_task_priority": "tasks.priority.set",
    "configure_budget": "scheduler.budget.configure",
    "run_schedule_once": "scheduler.run_once",
}
FALLBACK_CAPABILITY_MAP = {
    "scheduler.power_limit.set": ("tasks.pause",),
}


def _lookup_definition(registry, capability_name: str):
    try:
        return registry.get(capability_name).definition
    except KeyError as exc:
        raise ValueError(f"missing capability: {capability_name}") from exc


def _resolve_fallbacks(registry, capability_name: str) -> tuple[str, ...]:
    fallbacks = []
    for fallback_name in FALLBACK_CAPABILITY_MAP.get(capability_name, ()):
        try:
            registry.get(fallback_name)
        except KeyError:
            continue
        fallbacks.append(fallback_name)
    return tuple(fallbacks)


def _planned_actions(goal_spec) -> tuple[dict, ...]:
    if goal_spec.planner_actions:
        return tuple(goal_spec.planner_actions)
    heuristic = build_control_heuristic(goal_spec.raw_message)
    return tuple(heuristic.get("actions") or ())


def _build_action_steps(goal_spec, registry) -> tuple[PlanStep, ...]:
    steps = []
    for index, action in enumerate(_planned_actions(goal_spec), start=1):
        capability_name = ACTION_CAPABILITY_MAP.get(action.get("action", ""))
        if not capability_name:
            continue
        definition = _lookup_definition(registry, capability_name)
        steps.append(
            PlanStep(
                step_id=f"step-{index}",
                capability_name=capability_name,
                arguments=dict(action.get("target") or {}),
                approval_required=requires_approval(
                    definition,
                    goal_spec.permission_mode,
                ),
                fallback_capabilities=_resolve_fallbacks(
                    registry,
                    capability_name,
                ),
            )
        )
    return tuple(steps)


def build_initial_plan(goal_spec, registry) -> ExecutionPlan:
    read_definition = _lookup_definition(registry, "runtime.snapshot.read")
    read_step = PlanStep(
        step_id="step-read",
        capability_name=read_definition.name,
        arguments={},
        approval_required=False,
    )
    if goal_spec.goal_type == "analysis":
        return ExecutionPlan(
            plan_id=f"{goal_spec.session_id}-plan",
            steps=(read_step,),
            replan_budget=3,
        )

    action_steps = _build_action_steps(goal_spec, registry)
    if not action_steps:
        raise ValueError("no capability path for goal")
    return ExecutionPlan(
        plan_id=f"{goal_spec.session_id}-plan",
        steps=(read_step, *action_steps),
        replan_budget=3,
    )
