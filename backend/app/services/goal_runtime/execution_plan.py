from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    capability_name: str
    arguments: Mapping[str, object]
    approval_required: bool = False
    fallback_capabilities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "arguments",
            MappingProxyType(dict(self.arguments)),
        )
        object.__setattr__(
            self,
            "fallback_capabilities",
            tuple(self.fallback_capabilities),
        )


@dataclass(frozen=True)
class ExecutionPlan:
    plan_id: str
    steps: tuple[PlanStep, ...]
    replan_budget: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "steps", tuple(self.steps))

    def remaining_step_ids(self) -> tuple[str, ...]:
        return tuple(step.step_id for step in self.steps)

    def can_replan(self) -> bool:
        return self.replan_budget > 0
