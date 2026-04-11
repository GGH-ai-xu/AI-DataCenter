from __future__ import annotations

import json
from dataclasses import dataclass

from app.services.cluster_control.models import JobSpecRecord


PREEMPTABLE_JOB_STATUSES = frozenset({"running", "ready", "paused"})
PREEMPTABLE_LIFECYCLES = frozenset({"batch"})
TASK_KIND_RANK = {
    "maintenance": 0,
    "batch_compute": 1,
    "training": 2,
    "interactive_session": 3,
    "inference_service": 4,
}


@dataclass(frozen=True)
class VictimSelection:
    node_id: str
    job_id: str
    allocation_id: str
    device_ids: tuple[str, ...]


def _allocation_devices(allocation: dict) -> tuple[str, ...]:
    if "gpu_bindings" in allocation:
        return tuple(str(item) for item in (allocation.get("gpu_bindings") or ()))
    raw = allocation.get("gpu_bindings_json") or "[]"
    return tuple(str(item) for item in json.loads(raw))


def _job_resource(job: dict, key: str) -> int:
    request = job.get("resource_request") or {}
    return int(request.get(key, 0) or 0)


def _node_resource(node: dict, key: str) -> int:
    return int(node.get(f"{key}_free", 0) or 0)


def _freed_gpu_count(job: dict, allocation: dict) -> int:
    devices = _allocation_devices(allocation)
    if devices:
        return len(devices)
    return max(_job_resource(job, "gpu"), 1)


def _fits_after_release(
    target_job: JobSpecRecord,
    node: dict,
    victim_job: dict,
    victim_allocation: dict,
) -> bool:
    gpu_after = _node_resource(node, "gpu") + _freed_gpu_count(victim_job, victim_allocation)
    cpu_after = _node_resource(node, "cpu") + _job_resource(victim_job, "cpu")
    memory_after = _node_resource(node, "memory_bytes") + _job_resource(victim_job, "memory_bytes")
    return (
        gpu_after >= int(target_job.resource_request.get("gpu", 0) or 0)
        and cpu_after >= int(target_job.resource_request.get("cpu", 0) or 0)
        and memory_after >= int(target_job.resource_request.get("memory_bytes", 0) or 0)
    )


def _allow_preempt(job: dict, governance_rules: dict[str, dict]) -> bool:
    submitter_id = str(job.get("submitter_id") or "")
    rule = governance_rules.get(submitter_id) or {}
    return bool(rule.get("allow_preempt", True))


def _job_can_yield(
    target_job: JobSpecRecord,
    victim_job: dict,
    governance_rules: dict[str, dict],
) -> bool:
    if str(victim_job.get("status") or "") not in PREEMPTABLE_JOB_STATUSES:
        return False
    if not bool(victim_job.get("preemptible", False)):
        return False
    if not _allow_preempt(victim_job, governance_rules):
        return False
    if str(victim_job.get("lifecycle_kind") or "") not in PREEMPTABLE_LIFECYCLES:
        return False
    return int(target_job.priority) > int(victim_job.get("priority", 0) or 0)


def _candidate_sort_key(victim_job: dict, victim_allocation: dict) -> tuple[int, int, int, int, int]:
    runtime_profile = victim_job.get("runtime_profile") or {}
    return (
        TASK_KIND_RANK.get(str(victim_job.get("task_kind") or ""), 99),
        int(victim_job.get("priority", 0) or 0),
        0 if bool(runtime_profile.get("restartable", False)) else 1,
        1 if bool(runtime_profile.get("latency_sensitive", False)) else 0,
        -_freed_gpu_count(victim_job, victim_allocation),
    )


def _job_by_id(jobs: list[dict] | tuple[dict, ...]) -> dict[str, dict]:
    return {str(item.get("job_id") or ""): dict(item) for item in jobs}


def _node_allocations(
    node_id: str,
    allocations: list[dict] | tuple[dict, ...],
) -> list[dict]:
    return [
        dict(item)
        for item in allocations
        if str(item.get("node_id") or "") == node_id
        and str(item.get("status") or "") in {"active", "running", "paused", "checkpointing"}
    ]


def node_has_blockers(
    node_id: str,
    allocations: list[dict] | tuple[dict, ...],
) -> bool:
    return bool(_node_allocations(node_id, allocations))


def select_victim(
    *,
    target_job: JobSpecRecord,
    node: dict,
    jobs: list[dict] | tuple[dict, ...],
    allocations: list[dict] | tuple[dict, ...],
    governance_rules: dict[str, dict] | None = None,
) -> VictimSelection | None:
    job_map = _job_by_id(jobs)
    candidates: list[tuple[tuple[int, ...], dict, dict]] = []
    rules = dict(governance_rules or {})
    for allocation in _node_allocations(str(node.get("node_id") or ""), allocations):
        victim_job = job_map.get(str(allocation.get("job_id") or ""), {})
        if not _job_can_yield(target_job, victim_job, rules):
            continue
        if not _fits_after_release(target_job, node, victim_job, allocation):
            continue
        candidates.append((_candidate_sort_key(victim_job, allocation), victim_job, allocation))
    if not candidates:
        return None
    _, victim_job, victim_allocation = min(candidates, key=lambda item: item[0])
    return VictimSelection(
        node_id=str(node.get("node_id") or ""),
        job_id=str(victim_job.get("job_id") or ""),
        allocation_id=str(victim_allocation.get("allocation_id") or ""),
        device_ids=_allocation_devices(victim_allocation),
    )
