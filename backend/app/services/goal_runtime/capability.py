from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CapabilityManualControl:
    enabled: bool = False
    label: str = ""
    description: str = ""
    required_role: str = "member"
    risk_level: str = "observe"
    approval_policy: str = "direct"


@dataclass(frozen=True)
class CapabilityDefinition:
    name: str
    domain: str
    side_effect_level: str
    requires_scope: bool
    supported_providers: tuple[str, ...]
    manual_control: CapabilityManualControl = field(
        default_factory=CapabilityManualControl
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "supported_providers",
            tuple(self.supported_providers),
        )
