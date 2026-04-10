from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _normalize_arguments(arguments: Any) -> dict:
    if arguments is None:
        return {}
    return dict(arguments)


@dataclass(frozen=True)
class ControlCommandRecord:
    command_id: str
    capability_name: str
    domain: str
    operator_id: str
    operator_type: str
    workspace_key: str
    source_page: str
    arguments: dict
    risk_level: str
    permission_mode: str
    approval_state: str
    execution_state: str
    result_summary: str | None
    error_message: str | None
    related_session_id: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", _normalize_arguments(self.arguments))
        object.__setattr__(self, "result_summary", self.result_summary or "")
        object.__setattr__(self, "error_message", self.error_message or "")
        object.__setattr__(self, "related_session_id", self.related_session_id or "")
