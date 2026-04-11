from __future__ import annotations

from app.api.cluster_jobs import _load_cluster_nodes
from app.services.cluster_control.models import JobSpecRecord, PlacementPlan
from app.services.goal_runtime.capability import CapabilityDefinition


def _serialize_plan(plan: PlacementPlan) -> dict:
    return {
        "job_id": plan.job_id,
        "plan_type": plan.plan_type,
        "selected_node": plan.selected_node,
        "selected_devices": list(plan.selected_devices),
        "score_breakdown": dict(plan.score_breakdown),
        "execution_backend": plan.execution_backend,
        "alternatives": list(plan.alternatives),
        "reason": plan.reason,
    }


def _plan_only_job_record(arguments: dict) -> JobSpecRecord:
    return JobSpecRecord(
        job_id=str(arguments["job_id"]),
        tenant_id=str(arguments.get("tenant_id") or "default"),
        project_id=str(arguments.get("project_id") or "interactive"),
        queue_id=str(arguments.get("queue_id") or "default"),
        submitter_id=str(arguments.get("submitter_id") or "planner"),
        job_type=str(arguments.get("job_type") or "batch"),
        entrypoint=str(arguments.get("entrypoint") or "python train.py"),
        args=tuple(arguments.get("args", ())),
        env=dict(arguments.get("env", {})),
        resource_request=dict(arguments.get("resource_request", {})),
        placement_constraints=dict(arguments.get("placement_constraints", {})),
        priority=int(arguments.get("priority", 50)),
        preemptible=bool(arguments.get("preemptible", True)),
        max_retries=int(arguments.get("max_retries", 0)),
        timeout_seconds=int(arguments.get("timeout_seconds", 0)),
        task_kind=str(arguments.get("task_kind") or "batch_compute"),
        lifecycle_kind=str(arguments.get("lifecycle_kind") or "batch"),
        service_ports=tuple(arguments.get("service_ports", ())),
        checkpoint_policy=str(arguments.get("checkpoint_policy") or "none"),
        runtime_profile=dict(arguments.get("runtime_profile", {})),
    )


def register_cluster_planning_capabilities(
    registry,
    app_state,
    *,
    supported_providers: tuple[str, ...],
    manual_factory,
) -> None:
    async def plan_job(_context, arguments):
        nodes = await _load_cluster_nodes(app_state)
        plan = await app_state.cluster_control.plan_job(
            _plan_only_job_record(arguments),
            nodes=nodes,
        )
        return {"plan": _serialize_plan(plan)}

    async def plan_reschedule(_context, arguments):
        nodes = await _load_cluster_nodes(app_state)
        plan = await app_state.cluster_control.plan_reschedule(
            str(arguments["job_id"]),
            nodes=nodes,
        )
        return {"plan": _serialize_plan(plan)}

    registry.register(
        CapabilityDefinition(
            "job.plan",
            "jobs",
            "observe",
            False,
            supported_providers,
            manual_control=manual_factory(
                label="规划作业放置",
                description="预演指定 JobSpec 的放置结果，不会真正提交作业",
                required_role="observer",
            ),
        ),
        handler=plan_job,
    )
    registry.register(
        CapabilityDefinition(
            "reschedule.plan",
            "scheduler",
            "observe",
            False,
            supported_providers,
            manual_control=manual_factory(
                label="预演作业重排",
                description="查看现有作业的重排结果，不会真正迁移作业",
                required_role="observer",
            ),
        ),
        handler=plan_reschedule,
    )
