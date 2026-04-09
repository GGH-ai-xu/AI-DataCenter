from __future__ import annotations

from dataclasses import dataclass


def normalize_permission_mode(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "high":
        return "high"
    return "low"


def _normalize_scope_gpu_indexes(indexes: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(sorted({int(index) for index in indexes}))


@dataclass(frozen=True)
class GoalSpec:
    session_id: str
    raw_message: str
    goal_type: str
    permission_mode: str
    scope_gpu_indexes: tuple[int, ...]
    constraints: tuple[str, ...]
    done_when: str
    abort_when: tuple[str, ...]
    planner_actions: tuple[dict, ...] = ()
    planner_summary: str = ""
    planner_source: str = "rule"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "permission_mode",
            normalize_permission_mode(self.permission_mode),
        )
        object.__setattr__(
            self,
            "scope_gpu_indexes",
            _normalize_scope_gpu_indexes(self.scope_gpu_indexes),
        )
        object.__setattr__(self, "constraints", tuple(self.constraints))
        object.__setattr__(self, "abort_when", tuple(self.abort_when))
        object.__setattr__(
            self,
            "planner_actions",
            tuple(dict(action) for action in self.planner_actions),
        )
