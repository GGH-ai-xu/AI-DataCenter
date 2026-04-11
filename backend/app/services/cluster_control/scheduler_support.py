from __future__ import annotations

import json

from app.services.cluster_control.models import JobSpecRecord


ACTIVE_ALLOCATION_STATUSES = frozenset({"active", "paused", "running", "checkpointing"})


def runtime_profile_flag(job: JobSpecRecord, key: str) -> bool:
    return bool(job.runtime_profile.get(key, False))


def supported_lifecycle_kinds(node: dict) -> tuple[str, ...]:
    return tuple(str(item) for item in (node.get("supported_lifecycle_kinds") or ()))


def active_allocations_for_node(
    node_id: str,
    allocations: list[dict] | tuple[dict, ...],
) -> list[dict]:
    return [
        item
        for item in allocations
        if str(item.get("node_id") or "") == node_id
        and str(item.get("status") or "") in ACTIVE_ALLOCATION_STATUSES
    ]


def allocation_ports(allocation: dict) -> tuple[int, ...]:
    if "service_ports" in allocation:
        return tuple(int(item) for item in (allocation.get("service_ports") or ()))
    raw = allocation.get("service_ports_json") or "[]"
    return tuple(int(item) for item in json.loads(raw))


def allocation_devices(allocation: dict) -> tuple[str, ...]:
    if "gpu_bindings" in allocation:
        return tuple(str(item) for item in (allocation.get("gpu_bindings") or ()))
    raw = allocation.get("gpu_bindings_json") or "[]"
    return tuple(str(item) for item in json.loads(raw))


def prefers_headroom(job: JobSpecRecord) -> bool:
    if job.lifecycle_kind == "session":
        return True
    return job.lifecycle_kind == "service" and runtime_profile_flag(
        job,
        "latency_sensitive",
    )
