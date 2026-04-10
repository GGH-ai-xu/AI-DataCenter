from __future__ import annotations

import json
import shlex

from app.services.cluster_control.models import JobSpecRecord, PlacementPlan


class ExecutionOrchestrator:
    def __init__(self, store, backends: dict[str, object]):
        self.store = store
        self.backends = dict(backends)

    async def dispatch_plan(
        self,
        job_record: JobSpecRecord,
        plan: PlacementPlan,
        *,
        nodes: list[dict],
    ) -> dict:
        node = self._find_node(nodes, plan.selected_node)
        backend_name = self._backend_name(node, plan)
        backend = self._require_backend(backend_name)
        reservation = await backend.create_reservation(
            node,
            self._reservation_payload(job_record, plan),
        )
        launch = await backend.launch_job(
            node,
            self._launch_payload(job_record, reservation["reservation_id"]),
        )
        await self.store.create_cluster_allocation(
            self._allocation_payload(job_record, plan, backend_name, reservation),
        )
        await self.store.update_cluster_job_state(
            job_record.job_id,
            "running",
            execution_backend=backend_name,
        )
        return {"reservation": reservation, "launch": launch}

    def _find_node(self, nodes: list[dict], selected_node: str) -> dict:
        for node in nodes:
            if str(node["node_id"]) == selected_node:
                return node
        raise ValueError(f"selected node not found: {selected_node}")

    def _backend_name(self, node: dict, plan: PlacementPlan) -> str:
        return str(plan.execution_backend or node.get("execution_backend") or "http_agent")

    def _require_backend(self, backend_name: str):
        backend = self.backends.get(backend_name)
        if backend is None:
            raise ValueError(f"execution backend not configured: {backend_name}")
        return backend

    def _reservation_payload(
        self,
        job_record: JobSpecRecord,
        plan: PlacementPlan,
    ) -> dict:
        return {
            "reservation_id": f"res-{job_record.job_id}",
            "job_id": job_record.job_id,
            "gpu_indexes": self._gpu_indexes(plan.selected_devices),
            "cpu_cores": [],
        }

    def _launch_payload(self, job_record: JobSpecRecord, reservation_id: str) -> dict:
        return {
            "job_handle": f"handle-{job_record.job_id}",
            "job_id": job_record.job_id,
            "reservation_id": reservation_id,
            "command": self._command(job_record),
            "env": dict(job_record.env),
        }

    def _allocation_payload(
        self,
        job_record: JobSpecRecord,
        plan: PlacementPlan,
        backend_name: str,
        reservation: dict,
    ) -> dict:
        return {
            "allocation_id": f"alloc-{job_record.job_id}",
            "job_id": job_record.job_id,
            "reservation_id": reservation["reservation_id"],
            "node_id": plan.selected_node,
            "gpu_bindings_json": json.dumps(list(plan.selected_devices), ensure_ascii=False),
            "status": "active",
            "execution_backend": backend_name,
        }

    def _gpu_indexes(self, selected_devices: tuple[str, ...]) -> list[int]:
        indexes = []
        for device_id in selected_devices:
            suffix = str(device_id).split("-")[-1]
            indexes.append(int(suffix))
        return indexes

    def _command(self, job_record: JobSpecRecord) -> list[str]:
        return shlex.split(job_record.entrypoint) + list(job_record.args)
