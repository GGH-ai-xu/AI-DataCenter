from __future__ import annotations

from app.services.cluster_control.reclaim_runtime import request_reclaim_for_job
from app.services.cluster_control.models import JobSpecRecord, PlacementPlan
from app.services.cluster_control.reconcile_runtime import (
    dispatch_restore_plan,
    dispatch_placement_plan,
    persist_plan_outcome,
    should_restore_from_checkpoint,
)


async def _mark_victims_preempting(store, orchestrator, plan: PlacementPlan) -> list[dict]:
    results = []
    for job_id in plan.victim_job_ids:
        results.append(
            await request_reclaim_for_job(
                store,
                orchestrator,
                _find_job_allocation,
                store.get_cluster_job,
                job_id,
                plan_type=plan.plan_type,
                plan_reason=plan.reason,
            )
        )
    return results


async def _find_job_allocation(store, job_id: str, statuses: set[str]) -> dict | None:
    allocations = await store.list_cluster_allocations()
    for item in allocations:
        if str(item.get("job_id") or "") != job_id:
            continue
        if str(item.get("status") or "") not in statuses:
            continue
        return item
    return None


def _reclaim_summary_status(item: dict) -> str:
    checkpoint_status = str(item.get("checkpoint_status") or "")
    if checkpoint_status == "checkpoint_requested":
        return "checkpointing"
    return str(item.get("status") or "preempting")


def _consume_node_capacity(nodes: list[dict], plan: PlacementPlan, job_record: JobSpecRecord) -> None:
    for node in nodes:
        if str(node.get("node_id") or "") != str(plan.selected_node):
            continue
        node["gpu_free"] = max(
            0,
            int(node.get("gpu_free") or 0) - int(job_record.resource_request.get("gpu", 0) or 0),
        )
        node["cpu_free"] = max(
            0,
            int(node.get("cpu_free") or 0) - int(job_record.resource_request.get("cpu", 0) or 0),
        )
        node["memory_bytes_free"] = max(
            0,
            int(node.get("memory_bytes_free") or 0)
            - int(job_record.resource_request.get("memory_bytes", 0) or 0),
        )
        return


def _record_preemption_summary(summary: dict, plan: PlacementPlan, results: list[dict]) -> None:
    for item in results:
        summary["jobs"].append(
            {
                "job_id": str(item.get("job_id") or ""),
                "status": _reclaim_summary_status(item),
                "plan_type": plan.plan_type,
                "reason": plan.reason,
            }
        )
    summary["jobs"].append(
        {
            "job_id": plan.job_id,
            "status": "pending",
            "plan_type": plan.plan_type,
            "reason": plan.reason,
        }
    )


async def _start_preemption_wave(store, orchestrator, item: dict, plan: PlacementPlan) -> list[dict]:
    results = await _mark_victims_preempting(store, orchestrator, plan)
    await store.update_cluster_job_state(
        str(item.get("job_id") or ""),
        "pending",
        execution_backend="",
        plan_type=plan.plan_type,
        plan_reason=plan.reason,
        last_error="",
    )
    return results


async def execute_reconcile_decision(
    store,
    orchestrator,
    item: dict,
    job_record: JobSpecRecord,
    plan: PlacementPlan,
    nodes: list[dict],
    summary: dict,
) -> None:
    if plan.plan_type == "place":
        if should_restore_from_checkpoint(item):
            await dispatch_restore_plan(store, orchestrator, job_record, plan, nodes)
            _consume_node_capacity(nodes, plan, job_record)
            summary["dispatched"] += 1
            summary["jobs"].append(
                {"job_id": job_record.job_id, "status": "restoring", "plan_type": "place"}
            )
            return
        await dispatch_placement_plan(store, orchestrator, job_record, plan, nodes)
        _consume_node_capacity(nodes, plan, job_record)
        summary["dispatched"] += 1
        summary["jobs"].append(
            {"job_id": job_record.job_id, "status": "running", "plan_type": "place"}
        )
        return
    if plan.plan_type == "preempt_then_place":
        results = await _start_preemption_wave(store, orchestrator, item, plan)
        _record_preemption_summary(summary, plan, results)
        return
    await persist_plan_outcome(
        store,
        job_record.job_id,
        plan,
        current_status=str(item.get("status") or ""),
    )
