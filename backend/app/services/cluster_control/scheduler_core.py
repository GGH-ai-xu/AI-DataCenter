from __future__ import annotations

from app.services.cluster_control.models import JobSpecRecord, PlacementPlan
from app.services.cluster_control.preemption_selector import (
    node_has_blockers,
    select_victim,
)
from app.services.cluster_control.scheduler_support import (
    active_allocations_for_node,
    allocation_devices,
    allocation_ports,
    prefers_headroom,
    runtime_profile_flag,
    supported_lifecycle_kinds,
)


ACTIVE_QUEUE_STATE = "active"
CONCURRENCY_TRACKED_STATUSES = frozenset({"running", "paused", "ready"})
PLACE_PLAN = "place"
WAIT_PLAN = "wait"
REJECT_PLAN = "reject"
PREEMPT_THEN_PLACE_PLAN = "preempt_then_place"
HOLD_PLAN = "hold"


def _resource_need(job: JobSpecRecord, key: str) -> int:
    return int(job.resource_request.get(key, 0) or 0)


def _resource_free(node: dict, key: str) -> int:
    return int(node.get(f"{key}_free", 0) or 0)


def _build_device_ids(node: dict, gpu_need: int) -> tuple[str, ...]:
    available = tuple(node.get("device_ids") or ())
    if available:
        return available[:gpu_need]
    return tuple(f"gpu-{index}" for index in range(gpu_need))


class ClusterSchedulerCore:
    def plan_job(
        self,
        job: JobSpecRecord,
        nodes: list[dict],
        *,
        queue: dict | None = None,
        jobs: list[dict] | tuple[dict, ...] = (),
        allocations: list[dict] | tuple[dict, ...] = (),
        governance_rules: dict[str, dict] | None = None,
    ) -> PlacementPlan:
        admission_plan = self._queue_admission_plan(job, queue, jobs)
        if admission_plan is not None:
            return admission_plan
        candidates = self._schedulable_nodes(job, nodes, allocations)
        if not candidates:
            reclaim_plan = self._preemption_plan(
                job,
                nodes,
                jobs,
                allocations,
                governance_rules,
            )
            if reclaim_plan is not None:
                return reclaim_plan
            return PlacementPlan(
                job_id=job.job_id,
                plan_type=WAIT_PLAN,
                selected_node="",
                selected_devices=(),
                score_breakdown={"fit": 0.0},
                reason="no schedulable node satisfies current resource request",
            )
        best_node = min(candidates, key=self._placement_sort_key(job))
        gpu_need = _resource_need(job, "gpu")
        return PlacementPlan(
            job_id=job.job_id,
            plan_type=PLACE_PLAN,
            selected_node=str(best_node["node_id"]),
            selected_devices=_build_device_ids(best_node, gpu_need),
            score_breakdown=self._score_breakdown(job, best_node),
            execution_backend=str(best_node.get("execution_backend", "")),
            alternatives=tuple(str(node["node_id"]) for node in candidates[1:]),
            reason="best-fit schedulable node selected",
        )

    def _queue_admission_plan(
        self,
        job: JobSpecRecord,
        queue: dict | None,
        jobs: list[dict] | tuple[dict, ...],
    ) -> PlacementPlan | None:
        queue_record = dict(queue or {})
        queue_state = str(queue_record.get("state") or ACTIVE_QUEUE_STATE)
        if queue_state != ACTIVE_QUEUE_STATE:
            return PlacementPlan(
                job_id=job.job_id,
                plan_type=REJECT_PLAN,
                selected_node="",
                selected_devices=(),
                score_breakdown={"fit": 0.0},
                reason=f"queue {job.queue_id} is {queue_state}",
            )
        max_concurrency = int(queue_record.get("max_concurrency") or 0)
        if max_concurrency <= 0:
            return None
        active_jobs = self._active_queue_jobs(job, jobs)
        if len(active_jobs) < max_concurrency:
            return None
        return PlacementPlan(
            job_id=job.job_id,
            plan_type=WAIT_PLAN,
            selected_node="",
            selected_devices=(),
            score_breakdown={"fit": 0.0},
            reason=f"queue {job.queue_id} reached max_concurrency {max_concurrency}",
        )

    def _active_queue_jobs(
        self,
        job: JobSpecRecord,
        jobs: list[dict] | tuple[dict, ...],
    ) -> list[dict]:
        return [
            item
            for item in jobs
            if str(item.get("job_id") or "") != job.job_id
            and str(item.get("queue_id") or "") == job.queue_id
            and str(item.get("status") or "") in CONCURRENCY_TRACKED_STATUSES
        ]

    def _schedulable_nodes(
        self,
        job: JobSpecRecord,
        nodes: list[dict],
        allocations: list[dict] | tuple[dict, ...],
    ) -> list[dict]:
        return [node for node in nodes if self._matches_node(job, node, allocations)]

    def _matches_node(
        self,
        job: JobSpecRecord,
        node: dict,
        allocations: list[dict] | tuple[dict, ...],
    ) -> bool:
        if not bool(node.get("schedulable", False)):
            return False
        if str(node.get("drain_state") or "active") != "active":
            return False
        if not self._lifecycle_matches(job, node):
            return False
        if not self._resource_matches(job, node):
            return False
        if not self._ports_match(job, node, allocations):
            return False
        return self._exclusive_devices_match(job, node, allocations)

    def _lifecycle_matches(self, job: JobSpecRecord, node: dict) -> bool:
        supported = supported_lifecycle_kinds(node)
        return not supported or job.lifecycle_kind in supported

    def _resource_matches(self, job: JobSpecRecord, node: dict) -> bool:
        return (
            _resource_free(node, "gpu") >= _resource_need(job, "gpu")
            and _resource_free(node, "cpu") >= _resource_need(job, "cpu")
            and _resource_free(node, "memory_bytes")
            >= _resource_need(job, "memory_bytes")
        )

    def _ports_match(
        self,
        job: JobSpecRecord,
        node: dict,
        allocations: list[dict] | tuple[dict, ...],
    ) -> bool:
        requested_ports = set(job.service_ports)
        if not requested_ports:
            return True
        node_allocations = active_allocations_for_node(str(node["node_id"]), allocations)
        for allocation in node_allocations:
            if requested_ports.intersection(allocation_ports(allocation)):
                return False
        return True

    def _exclusive_devices_match(
        self,
        job: JobSpecRecord,
        node: dict,
        allocations: list[dict] | tuple[dict, ...],
    ) -> bool:
        if not runtime_profile_flag(job, "exclusive_gpu"):
            return True
        selected_devices = set(_build_device_ids(node, _resource_need(job, "gpu")))
        node_allocations = active_allocations_for_node(str(node["node_id"]), allocations)
        for allocation in node_allocations:
            if selected_devices.intersection(allocation_devices(allocation)):
                return False
        return True

    def _placement_sort_key(self, job: JobSpecRecord):
        def sort_key(node: dict) -> tuple[int, int, int, str]:
            gpu_surplus = _resource_free(node, "gpu") - _resource_need(job, "gpu")
            cpu_surplus = _resource_free(node, "cpu") - _resource_need(job, "cpu")
            memory_surplus = _resource_free(node, "memory_bytes") - _resource_need(job, "memory_bytes")
            if prefers_headroom(job):
                return (
                    -_resource_free(node, "gpu"),
                    -_resource_free(node, "cpu"),
                    -_resource_free(node, "memory_bytes"),
                    str(node["node_id"]),
                )
            return (gpu_surplus, cpu_surplus, memory_surplus, str(node["node_id"]))

        return sort_key

    def _score_breakdown(self, job: JobSpecRecord, node: dict) -> dict[str, float]:
        gpu_surplus = _resource_free(node, "gpu") - _resource_need(job, "gpu")
        cpu_surplus = _resource_free(node, "cpu") - _resource_need(job, "cpu")
        return {
            "fit": 1.0 / (1 + max(gpu_surplus, 0)),
            "cpu_headroom": float(max(cpu_surplus, 0)),
            "lifecycle_headroom": float(_resource_free(node, "gpu") + _resource_free(node, "cpu"))
            if prefers_headroom(job)
            else 0.0,
        }

    def _preemption_plan(
        self,
        job: JobSpecRecord,
        nodes: list[dict],
        jobs: list[dict] | tuple[dict, ...],
        allocations: list[dict] | tuple[dict, ...],
        governance_rules: dict[str, dict] | None,
    ) -> PlacementPlan | None:
        blockers_found = False
        for node in nodes:
            if not self._node_accepts_job(job, node):
                continue
            node_id = str(node.get("node_id") or "")
            blockers_found = blockers_found or node_has_blockers(node_id, allocations)
            victim = select_victim(
                target_job=job,
                node=node,
                jobs=jobs,
                allocations=allocations,
                governance_rules=governance_rules,
            )
            if victim is None:
                continue
            return PlacementPlan(
                job_id=job.job_id,
                plan_type=PREEMPT_THEN_PLACE_PLAN,
                selected_node=victim.node_id,
                selected_devices=victim.device_ids or _build_device_ids(node, _resource_need(job, "gpu")),
                score_breakdown={"fit": 1.0, "reclaim": 1.0},
                execution_backend=str(node.get("execution_backend", "")),
                reason=f"preempt job {victim.job_id} before placing target job",
                victim_job_ids=(victim.job_id,),
                victim_allocation_ids=(victim.allocation_id,),
                followup_job_ids=(job.job_id,),
                required_actions=(
                    {"action": "cancel_job", "job_id": victim.job_id},
                    {"action": "release_allocation", "allocation_id": victim.allocation_id},
                ),
            )
        if not blockers_found:
            return None
        return PlacementPlan(
            job_id=job.job_id,
            plan_type=HOLD_PLAN,
            selected_node="",
            selected_devices=(),
            score_breakdown={"fit": 0.0},
            reason="waiting for a reclaimable victim to appear",
        )

    def _node_accepts_job(self, job: JobSpecRecord, node: dict) -> bool:
        if not bool(node.get("schedulable", False)):
            return False
        if str(node.get("drain_state") or "active") != "active":
            return False
        return self._lifecycle_matches(job, node)
