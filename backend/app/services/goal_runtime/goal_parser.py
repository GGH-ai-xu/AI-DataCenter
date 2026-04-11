from __future__ import annotations

from app.services.goal_runtime.control_heuristics import build_control_heuristic
from app.services.goal_runtime.goal_spec import GoalSpec

JOB_ACTIONS = {
    "submit_job",
    "pause_job",
    "resume_job",
    "cancel_job",
    "checkpoint_job",
    "restore_job",
}


def _extract_constraints(message: str) -> tuple[str, ...]:
    lowered = (message or "").lower()
    constraints = []
    if "urgent" in lowered or "紧急" in message:
        constraints.append("do_not_interrupt_urgent_tasks")
    return tuple(constraints)


async def parse_goal_message(
    session_id: str,
    message: str,
    permission_mode: str,
    import_context,
    llm_service,
    planning_result: dict | None = None,
) -> GoalSpec:
    del llm_service
    normalized = (message or "").strip()
    planner_result = planning_result or build_control_heuristic(normalized)
    actions = planner_result.get("actions") or []
    goal_type = "runtime_control" if actions else "analysis"
    has_job_action = any(action.get("action") in JOB_ACTIONS for action in actions)
    if has_job_action:
        done_when = "job_state_updated"
    else:
        done_when = "goal_constraints_satisfied" if actions else "analysis_generated"
    planner_source = "llm" if planning_result else "rule"
    return GoalSpec(
        session_id=session_id,
        raw_message=normalized,
        goal_type=goal_type,
        permission_mode=permission_mode,
        scope_gpu_indexes=tuple(import_context.selected_gpu_indexes()),
        constraints=_extract_constraints(normalized),
        done_when=done_when,
        abort_when=("no_capability_path",),
        planner_actions=tuple(actions),
        planner_summary=str(planner_result.get("summary") or ""),
        planner_source=planner_source,
    )
