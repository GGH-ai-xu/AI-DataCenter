from __future__ import annotations

from app.services.cluster_control.checkpoint_history import load_restore_checkpoint
from app.services.cluster_control.models import JobSpecRecord, PlacementPlan


RECONCILEABLE_JOB_STATUSES = frozenset({"queued", "pending", "requeue_requested", "preempted"})


def build_job_spec_from_item(item: dict) -> JobSpecRecord:
    return JobSpecRecord(
        job_id=str(item["job_id"]),
        tenant_id=str(item["tenant_id"]),
        project_id=str(item["project_id"]),
        queue_id=str(item["queue_id"]),
        submitter_id=str(item["submitter_id"]),
        job_type=str(item["job_type"]),
        entrypoint=str(item["entrypoint"]),
        args=tuple(item.get("args", ())),
        env=dict(item.get("env", {})),
        resource_request=dict(item.get("resource_request", {})),
        placement_constraints=dict(item.get("placement_constraints", {})),
        priority=int(item.get("priority", 0)),
        preemptible=bool(item.get("preemptible", False)),
        max_retries=int(item.get("max_retries", 0)),
        timeout_seconds=int(item.get("timeout_seconds", 0)),
        task_kind=str(item.get("task_kind") or "batch_compute"),
        lifecycle_kind=str(item.get("lifecycle_kind") or "batch"),
        service_ports=tuple(item.get("service_ports", ())),
        checkpoint_policy=str(item.get("checkpoint_policy") or "none"),
        runtime_profile=dict(item.get("runtime_profile", {})),
    )


def build_planning_allocations(
    jobs: list[dict] | tuple[dict, ...],
    allocations: list[dict] | tuple[dict, ...],
    *,
    exclude_job_id: str = "",
) -> list[dict]:
    job_map = {str(item.get("job_id") or ""): item for item in jobs}
    enriched = []
    for allocation in allocations:
        job_id = str(allocation.get("job_id") or "")
        if exclude_job_id and job_id == exclude_job_id:
            continue
        job = job_map.get(job_id, {})
        enriched.append(
            {
                **allocation,
                "task_kind": str(job.get("task_kind") or ""),
                "lifecycle_kind": str(job.get("lifecycle_kind") or ""),
                "service_ports": list(job.get("service_ports") or ()),
                "runtime_profile": dict(job.get("runtime_profile") or {}),
            }
        )
    return enriched


async def load_queue(store, queue_id: str) -> dict:
    queue = await store.get_cluster_queue(queue_id)
    if queue is not None:
        return queue
    return {
        "queue_id": queue_id,
        "name": queue_id or "default",
        "state": "active",
        "default_priority": 0,
        "max_concurrency": 0,
    }


async def plan_existing_job(
    store,
    scheduler,
    item: dict,
    jobs: list[dict],
    nodes: list[dict],
    allocations: list[dict],
    governance_rules: dict[str, dict] | None = None,
) -> PlacementPlan:
    job_id = str(item.get("job_id") or "")
    siblings = [
        other
        for other in jobs
        if str(other.get("job_id") or "") != job_id
    ]
    return scheduler.plan_job(
        build_job_spec_from_item(item),
        nodes,
        queue=await load_queue(store, str(item.get("queue_id") or "")),
        jobs=siblings,
        allocations=build_planning_allocations(
            jobs,
            allocations,
            exclude_job_id=job_id,
        ),
        governance_rules=governance_rules,
    )


def _plan_status(current_status: str, plan_type: str) -> str:
    if plan_type == "reject":
        return "rejected"
    if plan_type == "requeue":
        return "requeue_requested"
    if current_status == "preempted" and plan_type in {"wait", "hold"}:
        return "preempted"
    if plan_type == "hold":
        return current_status or "pending"
    return "pending"


async def persist_plan_outcome(
    store,
    job_id: str,
    plan: PlacementPlan,
    *,
    current_status: str = "",
) -> None:
    if plan.plan_type == "place":
        return
    await store.update_cluster_job_state(
        job_id,
        _plan_status(current_status, plan.plan_type),
        execution_backend="",
        plan_type=plan.plan_type,
        plan_reason=plan.reason,
        last_error="",
    )


def resolve_backend_name(plan: PlacementPlan, nodes: list[dict]) -> str:
    if plan.execution_backend:
        return plan.execution_backend
    for node in nodes:
        if str(node.get("node_id") or "") != plan.selected_node:
            continue
        return str(node.get("execution_backend") or "")
    return ""


async def dispatch_placement_plan(
    store,
    orchestrator,
    job_record: JobSpecRecord,
    plan: PlacementPlan,
    nodes: list[dict],
) -> None:
    backend_name = resolve_backend_name(plan, nodes)
    await store.update_cluster_job_state(
        job_record.job_id,
        "dispatching",
        execution_backend=backend_name,
        plan_type=plan.plan_type,
        plan_reason=plan.reason,
        last_error="",
    )
    try:
        await orchestrator.dispatch_plan(job_record, plan, nodes=nodes)
    except Exception as exc:
        await store.update_cluster_job_state(
            job_record.job_id,
            "failed",
            execution_backend=backend_name,
            plan_type="dispatch_failed",
            plan_reason=str(exc),
            last_error=str(exc),
        )
        raise


async def dispatch_restore_plan(
    store,
    orchestrator,
    job_record: JobSpecRecord,
    plan: PlacementPlan,
    nodes: list[dict],
) -> None:
    checkpoint = await load_restore_checkpoint(store, job_record.job_id, "")
    backend_name = resolve_backend_name(plan, nodes)
    await store.update_cluster_job_state(
        job_record.job_id,
        "restoring",
        execution_backend=backend_name,
        plan_type=plan.plan_type,
        plan_reason=plan.reason,
        last_error="",
    )
    try:
        await orchestrator.restore_plan(
            job_record,
            plan,
            checkpoint,
            nodes=nodes,
        )
    except Exception as exc:
        await store.update_cluster_job_state(
            job_record.job_id,
            "failed",
            execution_backend=backend_name,
            plan_type="restore_failed",
            plan_reason=str(exc),
            last_error=str(exc),
        )
        raise


def should_restore_from_checkpoint(item: dict) -> bool:
    return (
        str(item.get("status") or "") == "preempted"
        and str(item.get("checkpoint_status") or "") == "checkpoint_ready"
        and bool(str(item.get("checkpoint_id") or ""))
    )


def record_plan_summary(summary: dict, job_id: str, plan: PlacementPlan) -> None:
    is_waiting = plan.plan_type in {"wait", "hold", "requeue"}
    summary["waiting" if is_waiting else "rejected"] += 1
    summary["jobs"].append(
        {
            "job_id": job_id,
            "status": "pending" if is_waiting else "rejected",
            "plan_type": plan.plan_type,
            "reason": plan.reason,
        }
    )


async def reconcile_one_job(
    store,
    scheduler,
    orchestrator,
    item: dict,
    jobs: list[dict],
    nodes: list[dict],
    allocations: list[dict],
    summary: dict,
) -> None:
    from app.services.cluster_control.reconcile_execution import (
        execute_reconcile_decision,
    )

    job_record = build_job_spec_from_item(item)
    governance_rules = await store.get_user_governance_rules()
    plan = await plan_existing_job(
        store,
        scheduler,
        item,
        jobs,
        nodes,
        allocations,
        governance_rules=governance_rules,
    )
    try:
        await execute_reconcile_decision(
            store,
            orchestrator,
            item,
            job_record,
            plan,
            nodes,
            summary,
        )
    except Exception as exc:
        summary["failed"] += 1
        summary["jobs"].append(
            {"job_id": job_record.job_id, "status": "failed", "error": str(exc)}
        )
        return
    if plan.plan_type in {"wait", "hold", "reject", "requeue"}:
        record_plan_summary(summary, job_record.job_id, plan)
