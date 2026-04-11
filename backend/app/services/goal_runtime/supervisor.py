from __future__ import annotations

from app.services.goal_runtime.executor import execute_capability
from app.services.goal_runtime.permission_policy import requires_approval


async def _append_event(
    persistence,
    session_id: str,
    event_type: str,
    payload: dict,
    *,
    round_index: int,
    sequence: int,
) -> str:
    await persistence.append_event(
        session_id,
        event_type,
        payload,
        round_index=round_index,
        sequence=sequence,
    )
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
    goal_spec,
    step,
    registry,
    execution_context: dict,
    emit_event,
) -> dict | None:
    for fallback_name in step.fallback_capabilities:
        await emit_event(
            "PlanRevised",
            {
                "step_id": step.step_id,
                "from_capability": step.capability_name,
                "to_capability": fallback_name,
            },
        )
        definition = registry.get(fallback_name).definition
        if requires_approval(definition, goal_spec.permission_mode):
            pending_approval = {"actions": [_pending_action(step, fallback_name)]}
            await emit_event("AwaitingApproval", pending_approval)
            return {
                "status": "awaiting_approval",
                "event_types": [],
                "pending_approval": pending_approval,
            }

        fallback_result = await execute_capability(
            registry,
            fallback_name,
            execution_context,
            dict(step.arguments),
        )
        if fallback_result["success"]:
            await emit_event(
                "StepCompleted",
                {
                    "step_id": step.step_id,
                    "capability_name": fallback_name,
                },
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
    *,
    round_index: int = 1,
    sequence_start: int = 1,
) -> dict:
    context = dict(execution_context or {})
    event_types: list[str] = []
    next_sequence = sequence_start

    async def emit_event(event_type: str, payload: dict) -> None:
        nonlocal next_sequence
        event_types.append(
            await _append_event(
                persistence,
                session_id,
                event_type,
                payload,
                round_index=round_index,
                sequence=next_sequence,
            )
        )
        next_sequence += 1

    for step in plan.steps:
        if step.approval_required:
            pending_approval = {"actions": [_pending_action(step, step.capability_name)]}
            await emit_event("AwaitingApproval", pending_approval)
            return {
                "status": "awaiting_approval",
                "event_types": event_types,
                "pending_approval": pending_approval,
            }

        await emit_event(
            "StepStarted",
            {
                "step_id": step.step_id,
                "capability_name": step.capability_name,
            },
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
            await emit_event(
                "StepCompleted",
                {
                    "step_id": step.step_id,
                    "capability_name": step.capability_name,
                },
            )
            continue

        fallback_state = await _handle_fallbacks(
            goal_spec,
            step,
            registry,
            context,
            emit_event,
        )
        if fallback_state is not None:
            if fallback_state["status"] == "completed":
                context = fallback_state["execution_context"]
                continue
            fallback_state["event_types"] = event_types
            return fallback_state

        await emit_event(
            "SessionFailed",
            {
                "step_id": step.step_id,
                "capability_name": step.capability_name,
                "error": result["error"],
            },
        )
        return {
            "status": "failed",
            "event_types": event_types,
            "error": result["error"],
        }

    await emit_event(
        "SessionCompleted",
        {
            "plan_id": plan.plan_id,
            "steps_completed": len(plan.steps),
        },
    )
    return {
        "status": "completed",
        "event_types": event_types,
    }
