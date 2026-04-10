from __future__ import annotations

from app.services.goal_runtime.executor import execute_capability
from app.services.goal_runtime.permission_policy import requires_approval


async def _append_event(
    persistence,
    session_id: str,
    event_type: str,
    payload: dict,
) -> str:
    await persistence.append_event(session_id, event_type, payload)
    return event_type


def _pending_action(step, capability_name: str) -> dict:
    return {
        "step_id": step.step_id,
        "capability_name": capability_name,
        "arguments": dict(step.arguments),
    }


def _update_execution_context(
    execution_context: dict,
    capability_name: str,
    output,
) -> dict:
    next_context = dict(execution_context)
    next_context["last_output"] = output
    if capability_name == "runtime.snapshot.read" and isinstance(output, dict):
        next_context["snapshot"] = output
        next_context["processes"] = output.get("processes", [])
    return next_context


async def _handle_fallbacks(
    session_id: str,
    goal_spec,
    step,
    registry,
    persistence,
    execution_context: dict,
    event_types: list[str],
) -> dict | None:
    for fallback_name in step.fallback_capabilities:
        event_types.append(
            await _append_event(
                persistence,
                session_id,
                "PlanRevised",
                {
                    "step_id": step.step_id,
                    "from_capability": step.capability_name,
                    "to_capability": fallback_name,
                },
            )
        )
        definition = registry.get(fallback_name).definition
        if requires_approval(definition, goal_spec.permission_mode):
            pending_approval = {"actions": [_pending_action(step, fallback_name)]}
            event_types.append(
                await _append_event(
                    persistence,
                    session_id,
                    "AwaitingApproval",
                    pending_approval,
                )
            )
            return {
                "status": "awaiting_approval",
                "event_types": event_types,
                "pending_approval": pending_approval,
            }

        fallback_result = await execute_capability(
            registry,
            fallback_name,
            execution_context,
            dict(step.arguments),
        )
        if fallback_result["success"]:
            event_types.append(
                await _append_event(
                    persistence,
                    session_id,
                    "StepCompleted",
                    {
                        "step_id": step.step_id,
                        "capability_name": fallback_name,
                    },
                )
            )
            return {
                "status": "completed",
                "execution_context": _update_execution_context(
                    execution_context,
                    fallback_name,
                    fallback_result.get("output"),
                ),
            }
    return None


async def execute_plan_session(
    session_id: str,
    goal_spec,
    plan,
    registry,
    persistence,
    execution_context: dict | None = None,
) -> dict:
    context = dict(execution_context or {})
    event_types: list[str] = []

    for step in plan.steps:
        if step.approval_required:
            pending_approval = {"actions": [_pending_action(step, step.capability_name)]}
            event_types.append(
                await _append_event(
                    persistence,
                    session_id,
                    "AwaitingApproval",
                    pending_approval,
                )
            )
            return {
                "status": "awaiting_approval",
                "event_types": event_types,
                "pending_approval": pending_approval,
            }

        event_types.append(
            await _append_event(
                persistence,
                session_id,
                "StepStarted",
                {
                    "step_id": step.step_id,
                    "capability_name": step.capability_name,
                },
            )
        )
        result = await execute_capability(
            registry,
            step.capability_name,
            context,
            dict(step.arguments),
        )
        if result["success"]:
            context = _update_execution_context(
                context,
                step.capability_name,
                result.get("output"),
            )
            event_types.append(
                await _append_event(
                    persistence,
                    session_id,
                    "StepCompleted",
                    {
                        "step_id": step.step_id,
                        "capability_name": step.capability_name,
                    },
                )
            )
            continue

        fallback_state = await _handle_fallbacks(
            session_id,
            goal_spec,
            step,
            registry,
            persistence,
            context,
            event_types,
        )
        if fallback_state is not None:
            if fallback_state["status"] == "completed":
                context = fallback_state["execution_context"]
                continue
            return fallback_state

        event_types.append(
            await _append_event(
                persistence,
                session_id,
                "SessionFailed",
                {
                    "step_id": step.step_id,
                    "capability_name": step.capability_name,
                    "error": result["error"],
                },
            )
        )
        return {
            "status": "failed",
            "event_types": event_types,
            "error": result["error"],
        }

    event_types.append(
        await _append_event(
            persistence,
            session_id,
            "SessionCompleted",
            {
                "plan_id": plan.plan_id,
                "steps_completed": len(plan.steps),
            },
        )
    )
    return {
        "status": "completed",
        "event_types": event_types,
    }
