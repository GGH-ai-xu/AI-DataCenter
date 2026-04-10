from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


def _freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


def _freeze_strings(value: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    return tuple(value or ())


@dataclass(frozen=True)
class NodeRecord:
    node_id: str
    cluster_id: str
    label: str
    state: str
    execution_backend: str
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True)
class DeviceRecord:
    device_id: str
    node_id: str
    device_type: str
    device_index: int
    pci_bus_id: str
    memory_bytes: int
    attributes: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "device_index", int(self.device_index))
        object.__setattr__(self, "memory_bytes", int(self.memory_bytes))
        object.__setattr__(self, "attributes", _freeze_mapping(self.attributes))


@dataclass(frozen=True)
class QueueRecord:
    queue_id: str
    name: str
    state: str
    default_priority: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "default_priority", int(self.default_priority))


@dataclass(frozen=True)
class JobSpecRecord:
    job_id: str
    tenant_id: str
    project_id: str
    queue_id: str
    submitter_id: str
    job_type: str
    entrypoint: str
    args: tuple[str, ...]
    env: Mapping[str, str]
    resource_request: Mapping[str, Any]
    placement_constraints: Mapping[str, Any]
    priority: int
    preemptible: bool
    max_retries: int
    timeout_seconds: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "args", _freeze_strings(self.args))
        object.__setattr__(self, "env", _freeze_mapping(self.env))
        object.__setattr__(
            self,
            "resource_request",
            _freeze_mapping(self.resource_request),
        )
        object.__setattr__(
            self,
            "placement_constraints",
            _freeze_mapping(self.placement_constraints),
        )
        object.__setattr__(self, "priority", int(self.priority))
        object.__setattr__(self, "preemptible", bool(self.preemptible))
        object.__setattr__(self, "max_retries", int(self.max_retries))
        object.__setattr__(self, "timeout_seconds", int(self.timeout_seconds))


@dataclass(frozen=True)
class JobRuntimeRecord:
    job_id: str
    status: str
    attempt: int
    node_id: str
    allocation_id: str
    last_error: str
    submitted_at: float
    started_at: float | None
    finished_at: float | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "attempt", int(self.attempt))


@dataclass(frozen=True)
class AllocationRecord:
    allocation_id: str
    job_id: str
    reservation_id: str
    node_id: str
    device_ids: tuple[str, ...]
    status: str
    execution_backend: str
    created_at: float
    updated_at: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "device_ids", _freeze_strings(self.device_ids))


@dataclass(frozen=True)
class ReservationRecord:
    reservation_id: str
    job_id: str
    node_id: str
    device_ids: tuple[str, ...]
    status: str
    created_at: float
    expires_at: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "device_ids", _freeze_strings(self.device_ids))


@dataclass(frozen=True)
class PlacementPlan:
    job_id: str
    plan_type: str
    selected_node: str
    selected_devices: tuple[str, ...]
    score_breakdown: Mapping[str, float]
    execution_backend: str = ""
    alternatives: tuple[str, ...] = ()
    reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "selected_devices", _freeze_strings(self.selected_devices))
        object.__setattr__(self, "score_breakdown", _freeze_mapping(self.score_breakdown))
        object.__setattr__(self, "alternatives", _freeze_strings(self.alternatives))
