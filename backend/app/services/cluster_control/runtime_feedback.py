from __future__ import annotations

from app.services.cluster_control.checkpoint_history import (
    build_checkpoint_record,
    build_job_checkpoint_pointer,
)


TERMINAL_RUNTIME_STATES = frozenset({"succeeded", "failed", "canceled"})
MONITORED_ALLOCATION_STATUSES = frozenset({"active", "releasing", "paused", "checkpointing"})


def _active_allocations_by_node(allocations: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for item in allocations:
        if str(item.get("status") or "") not in MONITORED_ALLOCATION_STATUSES:
            continue
        node_id = str(item.get("node_id") or "")
        grouped.setdefault(node_id, []).append(item)
    return grouped


def _jobs_by_handle(runtime_jobs: list[dict]) -> dict[str, dict]:
    return {
        str(item.get("job_handle") or ""): dict(item)
        for item in runtime_jobs
        if str(item.get("job_handle") or "")
    }


def _runtime_last_error(runtime_job: dict) -> str:
    last_error = str(runtime_job.get("last_error") or "")
    if last_error:
        return last_error
    exit_code = runtime_job.get("exit_code")
    if runtime_job.get("state") == "failed" and exit_code is not None:
        return f"runtime exited with code {exit_code}"
    return ""


async def release_runtime_resources(store, allocation: dict) -> None:
    await store.release_cluster_allocation(str(allocation["allocation_id"]))
    reservation_id = str(allocation.get("reservation_id") or "")
    if reservation_id:
        await store.update_cluster_reservation_status(reservation_id, "released")


async def apply_terminal_runtime_state(store, allocation: dict, runtime_job: dict) -> dict:
    job_id = str(allocation["job_id"])
    state = _job_terminal_state(
        await store.get_cluster_job(job_id),
        str(runtime_job.get("state") or ""),
    )
    await store.update_cluster_job_state(
        job_id,
        state,
        execution_backend=str(allocation.get("execution_backend") or ""),
        last_error=_runtime_last_error(runtime_job),
    )
    await release_runtime_resources(store, allocation)
    return {
        "job_id": job_id,
        "status": state,
        "error": _runtime_last_error(runtime_job),
    }


async def sync_runtime_job_state(store, allocation: dict, runtime_job: dict) -> None:
    checkpoint_state = str(runtime_job.get("checkpoint_state") or "")
    if not checkpoint_state:
        return
    record = build_checkpoint_record(
        str(allocation["job_id"]),
        allocation,
        runtime_job,
    )
    await store.upsert_cluster_checkpoint(record)
    await store.update_cluster_job_checkpoint(
        str(allocation["job_id"]),
        **build_job_checkpoint_pointer(record),
    )


async def _finish_checkpoint_reclaim(
    store,
    orchestrator,
    allocation: dict,
    runtime_job: dict,
    node: dict,
) -> dict | None:
    job = await store.get_cluster_job(str(allocation["job_id"]))
    if str((job or {}).get("status") or "") != "preempting":
        return None
    if str(runtime_job.get("checkpoint_state") or "") != "checkpoint_ready":
        return None
    runtime_job_handle = str(allocation.get("runtime_job_handle") or "")
    if not runtime_job_handle:
        raise ValueError(f"reclaiming job missing runtime handle: {allocation['job_id']}")
    terminal_job = await orchestrator.terminate_runtime_job(node, runtime_job_handle)
    return await apply_terminal_runtime_state(store, allocation, terminal_job)


def _job_terminal_state(job: dict | None, runtime_state: str) -> str:
    current_status = str((job or {}).get("status") or "")
    if runtime_state != "canceled":
        return runtime_state
    if current_status in {"preempting", "requeue_requested"}:
        return "preempted"
    return runtime_state


async def reconcile_runtime_feedback(store, orchestrator, nodes: list[dict]) -> dict:
    summary = {"completed": 0, "canceled": 0, "released": 0, "failed": 0, "jobs": []}
    grouped = _active_allocations_by_node(await store.list_cluster_allocations())
    nodes_by_id = {str(node.get("node_id") or ""): node for node in nodes}
    for node_id, allocations in grouped.items():
        node = nodes_by_id.get(node_id)
        if node is None:
            raise LookupError(f"cluster node not found for runtime reconciliation: {node_id}")
        runtime_jobs = _jobs_by_handle(await orchestrator.list_runtime_jobs(node))
        for allocation in allocations:
            runtime_job = runtime_jobs.get(str(allocation.get("runtime_job_handle") or ""))
            if runtime_job is None:
                continue
            await sync_runtime_job_state(store, allocation, runtime_job)
            reclaim_result = await _finish_checkpoint_reclaim(
                store,
                orchestrator,
                allocation,
                runtime_job,
                node,
            )
            if reclaim_result is not None:
                summary["released"] += 1
                summary["jobs"].append(reclaim_result)
                continue
            if str(runtime_job.get("state") or "") not in TERMINAL_RUNTIME_STATES:
                continue
            result = await apply_terminal_runtime_state(store, allocation, runtime_job)
            summary["released"] += 1
            summary["jobs"].append(result)
            if result["status"] == "succeeded":
                summary["completed"] += 1
            elif result["status"] == "canceled":
                summary["canceled"] += 1
            else:
                summary["failed"] += 1
    return summary


async def find_active_allocation_for_job(store, job_id: str) -> dict | None:
    allocations = await store.list_cluster_allocations()
    for item in allocations:
        if str(item.get("job_id") or "") != job_id:
            continue
        if str(item.get("status") or "") != "active":
            continue
        return item
    return None
