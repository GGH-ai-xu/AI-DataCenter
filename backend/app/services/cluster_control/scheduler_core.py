from __future__ import annotations

from app.services.cluster_control.models import JobSpecRecord, PlacementPlan


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
    ) -> PlacementPlan:
        candidates = self._schedulable_nodes(job, nodes)
        if not candidates:
            return PlacementPlan(
                job_id=job.job_id,
                plan_type="queue_wait",
                selected_node="",
                selected_devices=(),
                score_breakdown={"fit": 0.0},
                reason="no schedulable node satisfies current resource request",
            )
        best_node = min(candidates, key=self._placement_sort_key(job))
        gpu_need = _resource_need(job, "gpu")
        return PlacementPlan(
            job_id=job.job_id,
            plan_type="placement",
            selected_node=str(best_node["node_id"]),
            selected_devices=_build_device_ids(best_node, gpu_need),
            score_breakdown=self._score_breakdown(job, best_node),
            execution_backend=str(best_node.get("execution_backend", "")),
            alternatives=tuple(str(node["node_id"]) for node in candidates[1:]),
            reason="best-fit schedulable node selected",
        )

    def _schedulable_nodes(
        self,
        job: JobSpecRecord,
        nodes: list[dict],
    ) -> list[dict]:
        return [
            node
            for node in nodes
            if self._matches_node(job, node)
        ]

    def _matches_node(self, job: JobSpecRecord, node: dict) -> bool:
        if not bool(node.get("schedulable", False)):
            return False
        return (
            _resource_free(node, "gpu") >= _resource_need(job, "gpu")
            and _resource_free(node, "cpu") >= _resource_need(job, "cpu")
            and _resource_free(node, "memory_bytes") >= _resource_need(job, "memory_bytes")
        )

    def _placement_sort_key(self, job: JobSpecRecord):
        def sort_key(node: dict) -> tuple[int, int, int, str]:
            gpu_surplus = _resource_free(node, "gpu") - _resource_need(job, "gpu")
            cpu_surplus = _resource_free(node, "cpu") - _resource_need(job, "cpu")
            memory_surplus = _resource_free(node, "memory_bytes") - _resource_need(job, "memory_bytes")
            return (gpu_surplus, cpu_surplus, memory_surplus, str(node["node_id"]))

        return sort_key

    def _score_breakdown(self, job: JobSpecRecord, node: dict) -> dict[str, float]:
        gpu_surplus = _resource_free(node, "gpu") - _resource_need(job, "gpu")
        cpu_surplus = _resource_free(node, "cpu") - _resource_need(job, "cpu")
        return {
            "fit": 1.0 / (1 + max(gpu_surplus, 0)),
            "cpu_headroom": float(max(cpu_surplus, 0)),
        }
