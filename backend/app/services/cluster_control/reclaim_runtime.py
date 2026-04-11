from __future__ import annotations

import time

from app.services.cluster_control.checkpoint_history import (
    build_checkpoint_record,
    build_job_checkpoint_pointer,
)
from app.services.cluster_control.runtime_feedback import apply_terminal_runtime_state


DEFAULT_RECLAIM_CHECKPOINT_TIMEOUT_SECONDS = 30
PREEMPT_RECLAIM_PLAN_TYPE = "preempt_then_place"
CHECKPOINTING_ALLOCATION_STATUS = "checkpointing"


def supports_checkpoint_reclaim(job: dict) -> bool:
    return str(job.get("checkpoint_policy") or "") == "app_managed"


async def request_reclaim_for_job(
    store,
    orchestrator,
    allocation_finder,
    job_loader,
    job_id: str,
    *,
    plan_type: str,
    plan_reason: str,
) -> dict:
    job = await store.get_cluster_job(job_id)
    if job is None:
        raise LookupError(f"cluster job not found: {job_id}")
    allocation = await allocation_finder(store, job_id, {"active", "paused"})
    if allocation is None:
        raise ValueError(f"job missing allocation for reclaim: {job_id}")
    await store.update_cluster_job_state(
        job_id,
        "preempting",
        execution_backend=str(allocation.get("execution_backend") or ""),
        plan_type=plan_type,
        plan_reason=plan_reason,
        last_error="",
    )
    if not supports_checkpoint_reclaim(job):
        await _hard_reclaim_runtime_job(store, orchestrator, allocation, job_id)
        updated = await job_loader(job_id)
        if updated is None:
            raise LookupError(f"cluster job not found after reclaim mark: {job_id}")
        return updated
    updated = await _request_runtime_checkpoint(
        store,
        orchestrator,
        allocation,
        job_id,
    )
    await store.update_cluster_allocations_for_job(job_id, CHECKPOINTING_ALLOCATION_STATUS)
    latest = await job_loader(job_id)
    if latest is None:
        raise LookupError(f"cluster job not found after checkpoint reclaim: {job_id}")
    return latest


async def _hard_reclaim_runtime_job(
    store,
    orchestrator,
    allocation: dict,
    job_id: str,
) -> dict:
    node = await store.get_cluster_node(str(allocation["node_id"]))
    if node is None:
        raise LookupError(f"cluster node not found: {allocation['node_id']}")
    runtime_job_handle = str(allocation.get("runtime_job_handle") or "")
    if not runtime_job_handle:
        raise ValueError(f"job missing runtime handle for reclaim terminate: {job_id}")
    runtime_job = await orchestrator.terminate_runtime_job(node, runtime_job_handle)
    return await apply_terminal_runtime_state(store, allocation, runtime_job)


async def _request_runtime_checkpoint(
    store,
    orchestrator,
    allocation: dict,
    job_id: str,
) -> dict:
    node = await store.get_cluster_node(str(allocation["node_id"]))
    if node is None:
        raise LookupError(f"cluster node not found: {allocation['node_id']}")
    runtime_job_handle = str(allocation.get("runtime_job_handle") or "")
    if not runtime_job_handle:
        raise ValueError(f"job missing runtime handle for reclaim checkpoint: {job_id}")
    checkpoint_id = f"ckpt-{job_id}-{int(time.time())}"
    runtime_job = await orchestrator.checkpoint_runtime_job(
        node,
        runtime_job_handle,
        {
            "checkpoint_id": checkpoint_id,
            "timeout_seconds": DEFAULT_RECLAIM_CHECKPOINT_TIMEOUT_SECONDS,
        },
    )
    record = build_checkpoint_record(
        job_id,
        allocation,
        runtime_job,
        checkpoint_id=checkpoint_id,
        updated_at=time.time(),
    )
    await store.upsert_cluster_checkpoint(record)
    await store.update_cluster_job_checkpoint(
        job_id,
        **build_job_checkpoint_pointer(record),
    )
    return record
