from __future__ import annotations

import json
import shlex
import time

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
        reservation_payload = self._reservation_payload(job_record, plan)
        reservation = await backend.create_reservation(
            node,
            reservation_payload,
        )
        await self.store.create_cluster_reservation(
            self._reservation_record(
                plan.selected_node,
                reservation,
                reservation_payload,
            )
        )
        try:
            launch = await backend.launch_job(
                node,
                self._launch_payload(job_record, reservation["reservation_id"]),
            )
        except Exception:
            await self.store.update_cluster_reservation_status(
                reservation["reservation_id"],
                "failed",
            )
            raise
        await self.store.update_cluster_reservation_status(
            reservation["reservation_id"],
            "active",
        )
        await self.store.create_cluster_allocation(
            self._allocation_payload(
                job_record,
                plan,
                backend_name,
                reservation,
                launch,
            ),
        )
        await self.store.update_cluster_job_state(
            job_record.job_id,
            "running",
            execution_backend=backend_name,
            last_error="",
        )
        return {"reservation": reservation, "launch": launch}

    async def restore_plan(
        self,
        job_record: JobSpecRecord,
        plan: PlacementPlan,
        checkpoint: dict,
        *,
        nodes: list[dict],
    ) -> dict:
        node = self._find_node(nodes, plan.selected_node)
        backend_name = self._backend_name(node, plan)
        backend = self._require_backend(backend_name)
        reservation_payload = self._restore_reservation_payload(job_record, plan)
        reservation = await backend.create_reservation(node, reservation_payload)
        await self.store.create_cluster_reservation(
            self._reservation_record(
                plan.selected_node,
                reservation,
                reservation_payload,
            )
        )
        payload = self._restore_payload(
            job_record,
            checkpoint,
            reservation["reservation_id"],
            reservation_payload["job_handle"],
        )
        try:
            restore = await backend.restore_job(node, payload)
        except Exception:
            await self.store.update_cluster_reservation_status(
                reservation["reservation_id"],
                "failed",
            )
            raise
        await self.store.update_cluster_reservation_status(
            reservation["reservation_id"],
            "active",
        )
        await self.store.create_cluster_allocation(
            self._restore_allocation_payload(
                job_record,
                plan,
                backend_name,
                reservation,
                restore,
                reservation_payload["allocation_id"],
            ),
        )
        await self.store.update_cluster_job_state(
            job_record.job_id,
            "restoring",
            execution_backend=backend_name,
            last_error="",
        )
        return {"reservation": reservation, "restore": restore}

    async def list_runtime_jobs(self, node: dict) -> list[dict]:
        backend = self._runtime_backend(node)
        return await backend.list_jobs(node)

    async def get_runtime_job(self, node: dict, job_handle: str) -> dict:
        backend = self._runtime_backend(node)
        return await backend.get_job(node, job_handle)

    async def pause_runtime_job(self, node: dict, job_handle: str) -> dict:
        backend = self._runtime_backend(node)
        return await backend.pause_job(node, job_handle)

    async def resume_runtime_job(self, node: dict, job_handle: str) -> dict:
        backend = self._runtime_backend(node)
        return await backend.resume_job(node, job_handle)

    async def checkpoint_runtime_job(
        self,
        node: dict,
        job_handle: str,
        payload: dict,
    ) -> dict:
        backend = self._runtime_backend(node)
        return await backend.checkpoint_job(node, job_handle, payload)

    async def get_runtime_checkpoint(self, node: dict, job_handle: str) -> dict:
        backend = self._runtime_backend(node)
        return await backend.get_checkpoint(node, job_handle)

    async def restore_runtime_job(self, node: dict, payload: dict) -> dict:
        backend = self._runtime_backend(node)
        return await backend.restore_job(node, payload)

    async def terminate_runtime_job(self, node: dict, job_handle: str) -> dict:
        backend = self._runtime_backend(node)
        return await backend.terminate_job(node, job_handle)

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

    def _runtime_backend(self, node: dict):
        return self._require_backend(str(node.get("execution_backend") or "http_agent"))

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

    def _restore_reservation_payload(
        self,
        job_record: JobSpecRecord,
        plan: PlacementPlan,
    ) -> dict:
        suffix = int(time.time() * 1000)
        return {
            "reservation_id": f"res-{job_record.job_id}-{suffix}",
            "allocation_id": f"alloc-{job_record.job_id}-{suffix}",
            "job_handle": f"handle-{job_record.job_id}-{suffix}",
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
            "task_kind": job_record.task_kind,
            "lifecycle_kind": job_record.lifecycle_kind,
            "service_ports": list(job_record.service_ports),
            "checkpoint_policy": job_record.checkpoint_policy,
            "runtime_profile": dict(job_record.runtime_profile),
        }

    def _allocation_payload(
        self,
        job_record: JobSpecRecord,
        plan: PlacementPlan,
        backend_name: str,
        reservation: dict,
        launch: dict,
    ) -> dict:
        return {
            "allocation_id": f"alloc-{job_record.job_id}",
            "job_id": job_record.job_id,
            "reservation_id": reservation["reservation_id"],
            "node_id": plan.selected_node,
            "gpu_bindings_json": json.dumps(list(plan.selected_devices), ensure_ascii=False),
            "runtime_job_handle": str(launch.get("job_handle") or ""),
            "status": "active",
            "execution_backend": backend_name,
        }

    def _restore_allocation_payload(
        self,
        job_record: JobSpecRecord,
        plan: PlacementPlan,
        backend_name: str,
        reservation: dict,
        restore: dict,
        allocation_id: str,
    ) -> dict:
        return {
            "allocation_id": allocation_id,
            "job_id": job_record.job_id,
            "reservation_id": reservation["reservation_id"],
            "node_id": plan.selected_node,
            "gpu_bindings_json": json.dumps(list(plan.selected_devices), ensure_ascii=False),
            "runtime_job_handle": str(restore.get("job_handle") or ""),
            "status": "active",
            "execution_backend": backend_name,
        }

    def _reservation_record(
        self,
        node_id: str,
        reservation: dict,
        payload: dict,
    ) -> dict:
        return {
            "reservation_id": reservation["reservation_id"],
            "job_id": reservation["job_id"],
            "node_id": node_id,
            "device_ids": tuple(f"gpu-{index}" for index in payload["gpu_indexes"]),
            "status": "reserved",
        }

    def _gpu_indexes(self, selected_devices: tuple[str, ...]) -> list[int]:
        indexes = []
        for device_id in selected_devices:
            suffix = str(device_id).split("-")[-1]
            indexes.append(int(suffix))
        return indexes

    def _command(self, job_record: JobSpecRecord) -> list[str]:
        return shlex.split(job_record.entrypoint) + list(job_record.args)

    def _restore_payload(
        self,
        job_record: JobSpecRecord,
        checkpoint: dict,
        reservation_id: str,
        job_handle: str,
    ) -> dict:
        return {
            "job_handle": job_handle,
            "job_id": job_record.job_id,
            "reservation_id": reservation_id,
            "checkpoint_id": str(checkpoint["checkpoint_id"]),
            "manifest_path": str(checkpoint["manifest_path"]),
            "command": self._command(job_record),
            "env": dict(job_record.env),
            "working_dir": None,
            "task_kind": job_record.task_kind,
            "lifecycle_kind": job_record.lifecycle_kind,
            "service_ports": list(job_record.service_ports),
            "checkpoint_policy": job_record.checkpoint_policy,
            "runtime_profile": dict(job_record.runtime_profile),
        }
