from __future__ import annotations

from app.services.goal_runtime.goal_spec import normalize_permission_mode


RUNTIME_ACTION_LEVEL = "runtime_action"


def requires_approval(definition, permission_mode: str) -> bool:
    return (
        normalize_permission_mode(permission_mode) == "low"
        and definition.side_effect_level == RUNTIME_ACTION_LEVEL
    )
