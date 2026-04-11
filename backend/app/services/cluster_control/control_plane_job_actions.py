from __future__ import annotations

import shlex
import time

from app.services.cluster_control.checkpoint_history import (
    build_checkpoint_record,
    build_job_checkpoint_pointer,
    load_restore_checkpoint,
)
from app.services.cluster_control.reclaim_runtime import request_reclaim_for_job
from app.services.cluster_control.runtime_feedback import (
    apply_terminal_runtime_state,
    find_active_allocation_for_job,
)


REQUEUEABLE_JOB_STATUSES = frozenset({"running", "paused", "preempted"})
PREEMPTABLE_JOB_STATUSES = frozenset({"running", "ready"})
ALLOCATION_STATUS_BY_JOB_STATE = {
    "paused": "paused",
    "running": "active",
    "canceled": "canceled",
}


async def change_job_state(
    store,
    job_id: str,
    *,
    allowed_statuses: frozenset[str],
    next_status: str,
) -> dict:
    job = await store.get_cluster_job(job_id)
    if job is None:
        raise LookupError(f"cluster job not found: {job_id}")
    current_status = str(job.get("status") or "")
    if current_status not in allowed_statuses:
        raise ValueError(
            f"job {job_id} cannot transition from {current_status} to {next_status}"
        )
    await store.update_cluster_job_state(
        job_id,
        next_status,
        execution_backend=str(job.get("execution_backend") or ""),
    )
    await store.update_cluster_allocations_for_job(
        job_id,
        ALLOCATION_STATUS_BY_JOB_STATE[next_status],
    )
    updated = await store.get_cluster_job(job_id)
    if updated is None:
        raise LookupError(f"cluster job not found after update: {job_id}")
    return updated


async def change_node_drain_state(store, node_id: str, drain_state: str) -> dict:
    node = await store.get_cluster_node(node_id)
    if node is None:
        raise LookupError(f"cluster node not found: {node_id}")
    await store.update_cluster_node_drain_state(node_id, drain_state)
    updated = await store.get_cluster_node(node_id)
    if updated is None:
        raise LookupError(f"cluster node not found after update: {node_id}")
    return updated


async def reset_job_after_allocation_release(store, job_id: str) -> None:
    if not job_id:
        return
    job = await store.get_cluster_job(job_id)
    if job is None:
        return
    await store.update_cluster_job_state(
        job_id,
        "pending",
        execution_backend="",
    )


async def requeue_job(store, job_loader, job_id: str) -> dict:
    job = await store.get_cluster_job(job_id)
    if job is None:
        raise LookupError(f"cluster job not found: {job_id}")
    if str(job.get("lifecycle_kind") or "") != "batch":
        raise ValueError("only batch jobs support requeue")
    status = str(job.get("status") or "")
    if status not in REQUEUEABLE_JOB_STATUSES:
        raise ValueError(f"job {job_id} cannot requeue from {status}")
    await store.update_cluster_job_state(
        job_id,
        "requeue_requested",
        execution_backend="",
        plan_type="requeue",
        plan_reason="manual requeue requested",
        last_error="",
    )
    await store.update_cluster_allocations_for_job(job_id, "releasing")
    updated = await job_loader(job_id)
    if updated is None:
        raise LookupError(f"cluster job not found after requeue: {job_id}")
    return updated


async def preempt_job(store, orchestrator, job_loader, job_id: str) -> dict:
    job = await store.get_cluster_job(job_id)
    if job is None:
        raise LookupError(f"cluster job not found: {job_id}")
    if str(job.get("lifecycle_kind") or "") != "batch":
        raise ValueError("only batch jobs support preempt")
    status = str(job.get("status") or "")
    if status not in PREEMPTABLE_JOB_STATUSES:
        raise ValueError(f"job {job_id} cannot preempt from {status}")
    return await request_reclaim_for_job(
        store,
        orchestrator,
        _find_job_allocation,
        job_loader,
        job_id,
        plan_type="preempt",
        plan_reason="manual preemption requested",
    )


async def cancel_running_job(store, orchestrator, job_loader, job: dict) -> dict:
    job_id = str(job["job_id"])
    allocation = await find_active_allocation_for_job(store, job_id)
    if allocation is None:
        return await change_job_state(
            store,
            job_id,
            allowed_statuses=frozenset({"queued", "pending", "running", "paused"}),
            next_status="canceled",
        )
    runtime_job_handle = str(allocation.get("runtime_job_handle") or "")
    if not runtime_job_handle:
        raise ValueError(f"running job missing runtime handle: {job_id}")
    node = await store.get_cluster_node(str(allocation["node_id"]))
    if node is None:
        raise LookupError(f"cluster node not found: {allocation['node_id']}")
    runtime_job = await orchestrator.terminate_runtime_job(node, runtime_job_handle)
    await apply_terminal_runtime_state(store, allocation, runtime_job)
    updated = await job_loader(job_id)
    if updated is None:
        raise LookupError(f"cluster job not found after cancel: {job_id}")
    return updated


async def pause_running_job(store, orchestrator, job_loader, job: dict) -> dict:
    allocation = await find_active_allocation_for_job(store, str(job["job_id"]))
    if allocation is None:
        raise ValueError(f"running job missing active allocation: {job['job_id']}")
    node = await store.get_cluster_node(str(allocation["node_id"]))
    if node is None:
        raise LookupError(f"cluster node not found: {allocation['node_id']}")
    runtime_job_handle = str(allocation.get("runtime_job_handle") or "")
    if not runtime_job_handle:
        raise ValueError(f"running job missing runtime handle: {job['job_id']}")
    await orchestrator.pause_runtime_job(node, runtime_job_handle)
    await store.update_cluster_job_state(
        str(job["job_id"]),
        "paused",
        execution_backend=str(allocation.get("execution_backend") or ""),
    )
    await store.update_cluster_allocations_for_job(str(job["job_id"]), "paused")
    updated = await job_loader(str(job["job_id"]))
    if updated is None:
        raise LookupError(f"cluster job not found after pause: {job['job_id']}")
    return updated


async def resume_paused_job(store, orchestrator, job_loader, job: dict) -> dict:
    allocation = await _find_job_allocation(store, str(job["job_id"]), {"paused", "active"})
    if allocation is None:
        raise ValueError(f"paused job missing allocation: {job['job_id']}")
    node = await store.get_cluster_node(str(allocation["node_id"]))
    if node is None:
        raise LookupError(f"cluster node not found: {allocation['node_id']}")
    runtime_job_handle = str(allocation.get("runtime_job_handle") or "")
    if not runtime_job_handle:
        raise ValueError(f"paused job missing runtime handle: {job['job_id']}")
    runtime_job = await orchestrator.resume_runtime_job(node, runtime_job_handle)
    next_status = str(runtime_job.get("state") or "running")
    await store.update_cluster_job_state(
        str(job["job_id"]),
        next_status,
        execution_backend=str(allocation.get("execution_backend") or ""),
    )
    await store.update_cluster_allocations_for_job(str(job["job_id"]), "active")
    updated = await job_loader(str(job["job_id"]))
    if updated is None:
        raise LookupError(f"cluster job not found after resume: {job['job_id']}")
    return updated


async def request_checkpoint_for_job(
    store,
    orchestrator,
    job_loader,
    job: dict,
    *,
    timeout_seconds: int,
) -> dict:
    if str(job.get("checkpoint_policy") or "") != "app_managed":
        raise ValueError("job does not support app-managed checkpoint")
    allocation = await _find_job_allocation(store, str(job["job_id"]), {"active", "paused"})
    if allocation is None:
        raise ValueError(f"job missing allocation for checkpoint: {job['job_id']}")
    node = await store.get_cluster_node(str(allocation["node_id"]))
    if node is None:
        raise LookupError(f"cluster node not found: {allocation['node_id']}")
    runtime_job_handle = str(allocation.get("runtime_job_handle") or "")
    if not runtime_job_handle:
        raise ValueError(f"job missing runtime handle for checkpoint: {job['job_id']}")
    checkpoint_id = f"ckpt-{job['job_id']}-{int(time.time())}"
    runtime_job = await orchestrator.checkpoint_runtime_job(
        node,
        runtime_job_handle,
        {"checkpoint_id": checkpoint_id, "timeout_seconds": timeout_seconds},
    )
    record = build_checkpoint_record(
        str(job["job_id"]),
        allocation,
        runtime_job,
        checkpoint_id=checkpoint_id,
        updated_at=time.time(),
    )
    await store.upsert_cluster_checkpoint(record)
    await store.update_cluster_job_checkpoint(
        str(job["job_id"]),
        **build_job_checkpoint_pointer(record),
    )
    updated = await job_loader(str(job["job_id"]))
    if updated is None:
        raise LookupError(f"cluster job not found after checkpoint: {job['job_id']}")
    return updated


async def restore_checkpointed_job(
    store,
    orchestrator,
    job_loader,
    job: dict,
    *,
    checkpoint_id: str,
) -> dict:
    checkpoint = await load_restore_checkpoint(store, str(job["job_id"]), checkpoint_id)
    allocation = await _find_job_allocation(store, str(job["job_id"]), {"paused", "active"})
    if allocation is None:
        raise ValueError(f"job missing allocation for restore: {job['job_id']}")
    node = await store.get_cluster_node(str(allocation["node_id"]))
    if node is None:
        raise LookupError(f"cluster node not found: {allocation['node_id']}")
    payload = _build_restore_payload(
        job,
        allocation,
        str(checkpoint["checkpoint_id"]),
        str(checkpoint["manifest_path"]),
    )
    await orchestrator.restore_runtime_job(node, payload)
    await store.update_cluster_job_state(
        str(job["job_id"]),
        "restoring",
        execution_backend=str(allocation.get("execution_backend") or ""),
    )
    await store.update_cluster_allocations_for_job(str(job["job_id"]), "active")
    updated = await job_loader(str(job["job_id"]))
    if updated is None:
        raise LookupError(f"cluster job not found after restore: {job['job_id']}")
    return updated


async def _find_job_allocation(store, job_id: str, statuses: set[str]) -> dict | None:
    allocations = await store.list_cluster_allocations()
    for item in allocations:
        if str(item.get("job_id") or "") != job_id:
            continue
        if str(item.get("status") or "") not in statuses:
            continue
        return item
    return None


def _build_restore_payload(
    job: dict,
    allocation: dict,
    checkpoint_id: str,
    manifest_path: str,
) -> dict:
    return {
        "job_handle": str(allocation.get("runtime_job_handle") or f"handle-{job['job_id']}"),
        "job_id": str(job["job_id"]),
        "reservation_id": str(allocation.get("reservation_id") or f"res-{job['job_id']}"),
        "checkpoint_id": checkpoint_id,
        "manifest_path": manifest_path,
        "command": shlex.split(str(job.get("entrypoint") or "")) + list(job.get("args") or ()),
        "env": dict(job.get("env") or {}),
        "working_dir": None,
        "task_kind": str(job.get("task_kind") or "batch_compute"),
        "lifecycle_kind": str(job.get("lifecycle_kind") or "batch"),
        "service_ports": list(job.get("service_ports") or []),
        "checkpoint_policy": str(job.get("checkpoint_policy") or "none"),
        "runtime_profile": dict(job.get("runtime_profile") or {}),
    }
