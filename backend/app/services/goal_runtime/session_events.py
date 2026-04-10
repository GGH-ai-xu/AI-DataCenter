from __future__ import annotations

from dataclasses import dataclass
from time import time
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class SessionEvent:
    session_id: str
    event_type: str
    payload: Mapping[str, object]
    timestamp: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


def build_goal_parsed_event(
    session_id: str,
    goal_type: str,
    permission_mode: str,
    summary: str,
) -> SessionEvent:
    return SessionEvent(
        session_id=session_id,
        event_type="GoalParsed",
        payload={
            "goal_type": goal_type,
            "permission_mode": permission_mode,
            "summary": summary,
        },
        timestamp=time(),
    )
