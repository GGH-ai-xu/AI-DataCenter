from __future__ import annotations

import inspect


async def execute_capability(
    registry,
    capability_name: str,
    execution_context: dict,
    arguments: dict,
) -> dict:
    registered = registry.get(capability_name)
    try:
        outcome = registered.handler(execution_context, arguments)
        if inspect.isawaitable(outcome):
            outcome = await outcome
    except Exception as exc:
        return {
            "success": False,
            "capability_name": capability_name,
            "error": str(exc),
        }

    success = not (isinstance(outcome, dict) and outcome.get("success") is False)
    return {
        "success": success,
        "capability_name": capability_name,
        "output": outcome,
        "error": "" if success else str((outcome or {}).get("error", "")),
    }
