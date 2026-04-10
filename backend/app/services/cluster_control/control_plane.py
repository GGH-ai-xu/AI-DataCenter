from __future__ import annotations

from app.services.cluster_control.models import JobSpecRecord, PlacementPlan


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
        plan = self.scheduler.plan_job(job_record, nodes)
        if plan.plan_type == "placement":
            await self.orchestrator.dispatch_plan(job_record, plan, nodes=nodes)
        return plan

    async def list_queues(self) -> list[dict]:
        return await self.store.list_cluster_queues()

    async def list_jobs(self) -> list[dict]:
        return await self.store.list_cluster_jobs()

    async def get_job(self, job_id: str) -> dict | None:
        return await self.store.get_cluster_job(job_id)

    async def reconcile_queue(self, *, nodes: list[dict]) -> list[PlacementPlan]:
        plans = []
        for job in await self.store.list_cluster_jobs():
            if job.get("status") not in {"queued", "pending"}:
                continue
            plan = self.scheduler.plan_job(self._job_spec_from_item(job), nodes)
            plans.append(plan)
        return plans

    @staticmethod
    def _job_spec_from_item(item: dict) -> JobSpecRecord:
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
        )
