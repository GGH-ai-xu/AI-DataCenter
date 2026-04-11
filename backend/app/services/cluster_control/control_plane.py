from __future__ import annotations

from app.services.cluster_control.job_projection import (
    attach_runtime_handle_to_job,
    attach_runtime_handles_to_jobs,
)
from app.services.cluster_control.control_plane_job_actions import (
    cancel_running_job,
    change_job_state,
    change_node_drain_state,
    pause_running_job,
    preempt_job as preempt_cluster_job,
    requeue_job as requeue_cluster_job,
    reset_job_after_allocation_release,
    request_checkpoint_for_job,
    restore_checkpointed_job,
    resume_paused_job,
)
from app.services.cluster_control.models import JobSpecRecord, PlacementPlan
from app.services.cluster_control.reconcile_runtime import (
    RECONCILEABLE_JOB_STATUSES,
    build_planning_allocations,
    build_job_spec_from_item,
    dispatch_placement_plan,
    load_queue,
    persist_plan_outcome,
    plan_existing_job,
    reconcile_one_job,
)
from app.services.cluster_control.runtime_feedback import reconcile_runtime_feedback


PAUSABLE_JOB_STATUSES = frozenset({"running"})
RESUMABLE_JOB_STATUSES = frozenset({"paused"})
CANCELABLE_JOB_STATUSES = frozenset({"queued", "pending", "running", "paused"})


class ClusterControlPlaneService:
    def __init__(self, store, scheduler, orchestrator):
        self.store = store
        self.scheduler = scheduler
        self.orchestrator = orchestrator

    async def submit_job(
        self,
        job_record: JobSpecRecord,
        *,
        nodes: list[dict],
    ) -> PlacementPlan:
        await self.store.create_cluster_job(job_record)
        plan = await self.plan_job(job_record, nodes=nodes)
        if plan.plan_type == "place":
            await dispatch_placement_plan(
                self.store,
                self.orchestrator,
                job_record,
                plan,
                nodes,
            )
            return plan
        await persist_plan_outcome(
            self.store,
            job_record.job_id,
            plan,
            current_status="queued",
        )
        return plan

    async def plan_job(
        self,
        job_record: JobSpecRecord,
        *,
        nodes: list[dict],
    ) -> PlacementPlan:
        jobs = await self.store.list_cluster_jobs()
        governance_rules = await self.store.get_user_governance_rules()
        return self.scheduler.plan_job(
            job_record,
            nodes,
            queue=await load_queue(self.store, job_record.queue_id),
            jobs=jobs,
            allocations=build_planning_allocations(
                jobs,
                await self.store.list_cluster_allocations(),
            ),
            governance_rules=governance_rules,
        )

    async def plan_reschedule(
        self,
        job_id: str,
        *,
        nodes: list[dict],
    ) -> PlacementPlan:
        job = await self.store.get_cluster_job(job_id)
        if job is None:
            raise LookupError(f"cluster job not found: {job_id}")
        jobs = await self.store.list_cluster_jobs()
        allocations = await self.store.list_cluster_allocations()
        governance_rules = await self.store.get_user_governance_rules()
        return self.scheduler.plan_job(
            build_job_spec_from_item(job),
            nodes,
            queue=await load_queue(self.store, str(job.get("queue_id") or "")),
            jobs=[item for item in jobs if str(item.get("job_id") or "") != job_id],
            allocations=build_planning_allocations(
                jobs,
                allocations,
                exclude_job_id=job_id,
            ),
            governance_rules=governance_rules,
        )

    async def list_queues(self) -> list[dict]:
        return await self.store.list_cluster_queues()

    async def list_nodes(self) -> list[dict]:
        return await self.store.list_cluster_nodes()

    async def list_jobs(self) -> list[dict]:
        jobs = await self.store.list_cluster_jobs()
        allocations = await self.store.list_cluster_allocations()
        return attach_runtime_handles_to_jobs(jobs, allocations)

    async def get_job(self, job_id: str) -> dict | None:
        job = await self.store.get_cluster_job(job_id)
        allocations = await self.store.list_cluster_allocations()
        return attach_runtime_handle_to_job(job, allocations)

    async def list_job_checkpoints(self, job_id: str) -> list[dict]:
        job = await self.store.get_cluster_job(job_id)
        if job is None:
            raise LookupError(f"cluster job not found: {job_id}")
        return await self.store.list_cluster_checkpoints(job_id=job_id)

    async def get_checkpoint(self, checkpoint_id: str) -> dict | None:
        return await self.store.get_cluster_checkpoint(checkpoint_id)

    async def pause_job(self, job_id: str) -> dict:
        job = await self.store.get_cluster_job(job_id)
        if job is None:
            raise LookupError(f"cluster job not found: {job_id}")
        return await pause_running_job(self.store, self.orchestrator, self.get_job, job)

    async def resume_job(self, job_id: str) -> dict:
        job = await self.store.get_cluster_job(job_id)
        if job is None:
            raise LookupError(f"cluster job not found: {job_id}")
        return await resume_paused_job(self.store, self.orchestrator, self.get_job, job)

    async def checkpoint_job(self, job_id: str, *, timeout_seconds: int = 30) -> dict:
        job = await self.store.get_cluster_job(job_id)
        if job is None:
            raise LookupError(f"cluster job not found: {job_id}")
        return await request_checkpoint_for_job(
            self.store,
            self.orchestrator,
            self.get_job,
            job,
            timeout_seconds=timeout_seconds,
        )

    async def restore_job(self, job_id: str, *, checkpoint_id: str = "") -> dict:
        job = await self.store.get_cluster_job(job_id)
        if job is None:
            raise LookupError(f"cluster job not found: {job_id}")
        return await restore_checkpointed_job(
            self.store,
            self.orchestrator,
            self.get_job,
            job,
            checkpoint_id=checkpoint_id,
        )

    async def cancel_job(self, job_id: str) -> dict:
        job = await self.store.get_cluster_job(job_id)
        if job is None:
            raise LookupError(f"cluster job not found: {job_id}")
        if str(job.get("status") or "") == "running":
            return await cancel_running_job(
                self.store,
                self.orchestrator,
                self.get_job,
                job,
            )
        return await change_job_state(
            self.store,
            job_id,
            allowed_statuses=CANCELABLE_JOB_STATUSES,
            next_status="canceled",
        )

    async def requeue_job(self, job_id: str) -> dict:
        return await requeue_cluster_job(self.store, self.get_job, job_id)

    async def preempt_job(self, job_id: str) -> dict:
        return await preempt_cluster_job(
            self.store,
            self.orchestrator,
            self.get_job,
            job_id,
        )

    async def drain_node(self, node_id: str) -> dict:
        return await change_node_drain_state(self.store, node_id, "drained")

    async def undrain_node(self, node_id: str) -> dict:
        return await change_node_drain_state(self.store, node_id, "active")

    async def release_allocation(self, allocation_id: str) -> dict:
        allocation = await self.store.get_cluster_allocation(allocation_id)
        if allocation is None:
            raise LookupError(f"cluster allocation not found: {allocation_id}")
        await self.store.release_cluster_allocation(allocation_id)
        await reset_job_after_allocation_release(
            self.store,
            str(allocation.get("job_id") or ""),
        )
        updated = await self.store.get_cluster_allocation(allocation_id)
        if updated is None:
            raise LookupError(f"cluster allocation not found after update: {allocation_id}")
        return updated

    async def reconcile_queue(self, *, nodes: list[dict]) -> list[PlacementPlan]:
        plans = []
        jobs = sorted(
            await self.store.list_cluster_jobs(),
            key=lambda item: (
                -int(item.get("priority") or 0),
                str(item.get("job_id") or ""),
            ),
        )
        allocations = await self.store.list_cluster_allocations()
        for job in jobs:
            if job.get("status") not in RECONCILEABLE_JOB_STATUSES:
                continue
            plans.append(
                await plan_existing_job(
                    self.store,
                    self.scheduler,
                    job,
                    jobs,
                    nodes,
                    allocations,
                )
            )
        return plans

    async def reconcile_and_dispatch(self, *, nodes: list[dict]) -> dict:
        summary = {
            "processed": 0,
            "dispatched": 0,
            "waiting": 0,
            "rejected": 0,
            "failed": 0,
            "completed": 0,
            "canceled": 0,
            "released": 0,
            "jobs": [],
        }
        runtime_summary = await reconcile_runtime_feedback(
            self.store,
            self.orchestrator,
            nodes,
        )
        summary["failed"] += runtime_summary["failed"]
        summary["completed"] = runtime_summary["completed"]
        summary["canceled"] = runtime_summary["canceled"]
        summary["released"] = runtime_summary["released"]
        summary["jobs"].extend(runtime_summary["jobs"])
        jobs = sorted(
            await self.store.list_cluster_jobs(),
            key=lambda item: (
                -int(item.get("priority") or 0),
                str(item.get("job_id") or ""),
            ),
        )
        allocations = await self.store.list_cluster_allocations()
        for item in jobs:
            if str(item.get("status") or "") not in RECONCILEABLE_JOB_STATUSES:
                continue
            summary["processed"] += 1
            await reconcile_one_job(
                self.store,
                self.scheduler,
                self.orchestrator,
                item,
                jobs,
                nodes,
                allocations,
                summary,
            )
        return summary
