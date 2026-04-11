import os
import sys
import types
import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.cluster_control.control_plane import (  # noqa: E402
    ClusterControlPlaneService,
)
from app.services.cluster_control.models import PlacementPlan  # noqa: E402
from app.services.cluster_control.scheduler_core import ClusterSchedulerCore  # noqa: E402


class _FakeStore:
    def __init__(self):
        self.created_job_records = []
        self.jobs = {}
        self.queues = [
            {
                "queue_id": "default",
                "name": "Default",
                "state": "active",
                "default_priority": 50,
            }
        ]
        self.allocations = []
        self.nodes = [
            {
                "node_id": "node-a",
                "cluster_id": "cluster-a",
                "label": "Node A",
                "state": "ready",
                "drain_state": "active",
                "execution_backend": "http_agent",
                "metadata": {},
            }
        ]

    async def create_cluster_job(self, record):
        self.created_job_records.append(record)
        self.jobs[record.job_id] = {
            "job_id": record.job_id,
            "queue_id": record.queue_id,
            "tenant_id": record.tenant_id,
            "project_id": record.project_id,
            "submitter_id": record.submitter_id,
            "job_type": record.job_type,
            "entrypoint": record.entrypoint,
            "status": "queued",
            "priority": record.priority,
            "task_kind": str(getattr(record, "task_kind", "")),
            "lifecycle_kind": str(getattr(record, "lifecycle_kind", "")),
            "service_ports": list(getattr(record, "service_ports", ())),
            "checkpoint_policy": str(getattr(record, "checkpoint_policy", "")),
            "checkpoint_id": "",
            "checkpoint_status": "",
            "checkpoint_manifest_path": "",
            "checkpoint_error": "",
            "runtime_profile": dict(getattr(record, "runtime_profile", {})),
        }

    async def update_cluster_job_state(self, job_id, status, *, execution_backend=""):
        self.jobs[job_id]["status"] = status
        self.jobs[job_id]["execution_backend"] = execution_backend

    async def create_cluster_allocation(self, payload):
        self.allocations.append(dict(payload))

    async def get_cluster_job(self, job_id):
        return self.jobs.get(job_id)

    async def list_cluster_jobs(self):
        return list(self.jobs.values())

    async def list_cluster_queues(self):
        return list(self.queues)

    async def list_cluster_allocations(self):
        return list(self.allocations)

    async def list_cluster_nodes(self):
        return list(self.nodes)

    async def upsert_cluster_node(self, payload):
        for index, item in enumerate(self.nodes):
            if item["node_id"] == payload["node_id"]:
                self.nodes[index] = {**item, **payload}
                return
        self.nodes.append(dict(payload))

    async def get_cluster_node(self, node_id):
        for item in self.nodes:
            if item["node_id"] == node_id:
                return dict(item)
        return None


class _FakeControlPlane:
    def __init__(self, store):
        self.store = store

    async def submit_job(self, job_record, *, nodes):
        await self.store.create_cluster_job(job_record)
        plan = PlacementPlan(
            job_id=job_record.job_id,
            plan_type="placement",
            selected_node=str(nodes[0]["node_id"]),
            selected_devices=("gpu-0",),
            score_breakdown={"fit": 1.0},
            execution_backend="http_agent",
        )
        await self.store.update_cluster_job_state(
            job_record.job_id,
            "running",
            execution_backend="http_agent",
        )
        await self.store.create_cluster_allocation(
            {
                "allocation_id": f"alloc-{job_record.job_id}",
                "job_id": job_record.job_id,
                "node_id": plan.selected_node,
                "gpu_bindings_json": "[\"gpu-0\"]",
                "status": "active",
                "execution_backend": "http_agent",
            }
        )
        return plan

    async def list_queues(self):
        return await self.store.list_cluster_queues()

    async def list_jobs(self):
        return list(self.store.jobs.values())

    async def get_job(self, job_id):
        return await self.store.get_cluster_job(job_id)

    async def pause_job(self, job_id):
        self.store.jobs[job_id]["status"] = "paused"
        return dict(self.store.jobs[job_id])

    async def resume_job(self, job_id):
        self.store.jobs[job_id]["status"] = "running"
        return dict(self.store.jobs[job_id])

    async def checkpoint_job(self, job_id, *, timeout_seconds=30):
        self.store.jobs[job_id]["checkpoint_id"] = "ckpt-job-1"
        self.store.jobs[job_id]["checkpoint_status"] = "checkpoint_requested"
        self.store.jobs[job_id]["checkpoint_timeout_seconds"] = int(timeout_seconds)
        return dict(self.store.jobs[job_id])

    async def restore_job(self, job_id, *, checkpoint_id=""):
        self.store.jobs[job_id]["status"] = "restoring"
        self.store.jobs[job_id]["checkpoint_id"] = checkpoint_id or "ckpt-job-1"
        return dict(self.store.jobs[job_id])

    async def drain_node(self, node_id):
        for item in self.store.nodes:
            if item["node_id"] == node_id:
                item["drain_state"] = "drained"
                return dict(item)
        raise LookupError("cluster node not found")

    async def undrain_node(self, node_id):
        for item in self.store.nodes:
            if item["node_id"] == node_id:
                item["drain_state"] = "active"
                return dict(item)
        raise LookupError("cluster node not found")

    async def release_allocation(self, allocation_id):
        for item in self.store.allocations:
            if item["allocation_id"] == allocation_id:
                item["status"] = "released"
                return dict(item)
        raise LookupError("cluster allocation not found")

    async def reconcile_and_dispatch(self, *, nodes):
        return {
            "processed": 1,
            "dispatched": 1,
            "waiting": 0,
            "rejected": 0,
            "failed": 0,
            "jobs": [{"job_id": "job-1", "status": "running"}],
        }


class _FakeReconcileController:
    def __init__(self):
        self.enabled = False
        self.interval_seconds = 15.0
        self.last_trigger = ""
        self.last_summary = {}

    def snapshot(self):
        return {
            "enabled": self.enabled,
            "running": False,
            "interval_seconds": self.interval_seconds,
            "tick_count": 0,
            "last_trigger": self.last_trigger,
            "last_started_at": 0,
            "last_finished_at": 0,
            "last_error": "",
            "last_skip_reason": "",
            "last_summary": dict(self.last_summary),
        }

    def configure(self, *, enabled=None, interval_seconds=None):
        if enabled is not None:
            self.enabled = bool(enabled)
        if interval_seconds is not None:
            self.interval_seconds = float(interval_seconds)
        return self.snapshot()

    async def run_once(self, *, trigger):
        self.last_trigger = trigger
        self.last_summary = {
            "processed": 1,
            "dispatched": 1,
            "waiting": 0,
            "rejected": 0,
            "failed": 0,
            "jobs": [{"job_id": "job-1", "status": "running"}],
        }
        return self.last_summary


class ClusterJobApiTests(unittest.TestCase):
    def setUp(self):
        from app.api.cluster_jobs import router as jobs_router
        from app.api.cluster_queues import router as queues_router

        self.store = _FakeStore()
        fake_state = types.SimpleNamespace(
            cluster_control=_FakeControlPlane(self.store),
            cluster_reconcile_controller=_FakeReconcileController(),
            store=self.store,
            cluster_nodes=[
                {
                    "node_id": "node-a",
                    "schedulable": True,
                    "gpu_free": 1,
                    "cpu_free": 16,
                    "execution_backend": "http_agent",
                    "base_url": "http://127.0.0.1:8001",
                }
            ],
        )
        self.fake_main = types.SimpleNamespace(app_state=fake_state)
        app = FastAPI()
        app.include_router(jobs_router)
        app.include_router(queues_router)
        self.client = TestClient(app)

    def test_submit_job_returns_running_record(self):
        with mock.patch.dict(sys.modules, {"app.main": self.fake_main}):
            response = self.client.post(
                "/api/cluster/jobs",
                json={
                    "job_id": "job-1",
                    "tenant_id": "tenant-a",
                    "project_id": "project-a",
                    "queue_id": "default",
                    "submitter_id": "alice",
                    "job_type": "batch",
                    "entrypoint": "python train.py",
                    "args": [],
                    "env": {},
                    "resource_request": {"gpu": 1, "cpu": 4},
                    "placement_constraints": {},
                    "priority": 50,
                    "preemptible": True,
                    "max_retries": 1,
                    "timeout_seconds": 600,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "running")

    def test_submit_job_persists_unified_task_fields(self):
        with mock.patch.dict(sys.modules, {"app.main": self.fake_main}):
            response = self.client.post(
                "/api/cluster/jobs",
                json={
                    "job_id": "job-service-1",
                    "tenant_id": "tenant-a",
                    "project_id": "project-a",
                    "queue_id": "default",
                    "submitter_id": "alice",
                    "job_type": "service",
                    "task_kind": "inference_service",
                    "lifecycle_kind": "service",
                    "entrypoint": "python serve.py",
                    "args": ["--port", "8080"],
                    "env": {"MODEL_ID": "qwen"},
                    "resource_request": {"gpu": 1, "cpu": 4},
                    "placement_constraints": {"node_group": "service"},
                    "priority": 80,
                    "preemptible": False,
                    "max_retries": 0,
                    "timeout_seconds": 0,
                    "service_ports": [8080, 9090],
                    "checkpoint_policy": "none",
                    "runtime_profile": {
                        "latency_sensitive": True,
                        "restartable": False,
                        "exclusive_gpu": True,
                        "expected_duration_seconds": 0,
                    },
                },
            )

        self.assertEqual(response.status_code, 200)
        job = self.store.jobs["job-service-1"]
        self.assertEqual(job["task_kind"], "inference_service")
        self.assertEqual(job["lifecycle_kind"], "service")
        self.assertEqual(job["service_ports"], [8080, 9090])
        self.assertEqual(job["checkpoint_policy"], "none")
        self.assertEqual(job["runtime_profile"].get("latency_sensitive"), True)
        self.assertEqual(job["runtime_profile"].get("exclusive_gpu"), True)

    def test_list_queues_and_allocations(self):
        with mock.patch.dict(sys.modules, {"app.main": self.fake_main}):
            queues = self.client.get("/api/cluster/queues")
            allocations = self.client.get("/api/cluster/allocations")

        self.assertEqual(queues.status_code, 200)
        self.assertEqual(queues.json()["queues"][0]["queue_id"], "default")
        self.assertEqual(allocations.status_code, 200)
        self.assertEqual(allocations.json()["allocations"], [])

    def test_cluster_object_control_routes_mutate_node_and_allocation_state(self):
        with mock.patch.dict(sys.modules, {"app.main": self.fake_main}):
            self.client.post(
                "/api/cluster/jobs",
                json={
                    "job_id": "job-1",
                    "tenant_id": "tenant-a",
                    "project_id": "project-a",
                    "queue_id": "default",
                    "submitter_id": "alice",
                    "job_type": "batch",
                    "entrypoint": "python train.py",
                    "args": [],
                    "env": {},
                    "resource_request": {"gpu": 1},
                    "placement_constraints": {},
                    "priority": 50,
                    "preemptible": True,
                    "max_retries": 1,
                    "timeout_seconds": 600,
                },
            )
            drain_response = self.client.post("/api/cluster/nodes/node-a/drain")
            release_response = self.client.post("/api/cluster/allocations/alloc-job-1/release")
            undrain_response = self.client.post("/api/cluster/nodes/node-a/undrain")

        self.assertEqual(drain_response.status_code, 200)
        self.assertEqual(drain_response.json()["drain_state"], "drained")
        self.assertEqual(release_response.status_code, 200)
        self.assertEqual(release_response.json()["status"], "released")
        self.assertEqual(undrain_response.status_code, 200)
        self.assertEqual(undrain_response.json()["drain_state"], "active")

    def test_cluster_reconcile_route_returns_dispatch_summary(self):
        with mock.patch.dict(sys.modules, {"app.main": self.fake_main}):
            response = self.client.post("/api/cluster/reconcile")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["dispatched"], 1)
        self.assertEqual(response.json()["jobs"][0]["status"], "running")
        self.assertEqual(
            self.fake_main.app_state.cluster_reconcile_controller.last_trigger,
            "manual",
        )

    def test_cluster_controller_status_and_config_routes(self):
        with mock.patch.dict(sys.modules, {"app.main": self.fake_main}):
            status = self.client.get("/api/cluster/controller")
            updated = self.client.post(
                "/api/cluster/controller",
                json={"enabled": True, "interval_seconds": 5},
            )

        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["enabled"], False)
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["enabled"], True)
        self.assertEqual(updated.json()["interval_seconds"], 5)

    def test_list_jobs_surfaces_releasing_allocation_projection(self):
        self.store.jobs["job-preempting"] = {
            "job_id": "job-preempting",
            "queue_id": "default",
            "tenant_id": "tenant-a",
            "project_id": "project-a",
            "submitter_id": "alice",
            "job_type": "batch",
            "entrypoint": "python train.py",
            "status": "preempting",
            "priority": 90,
            "task_kind": "training",
            "lifecycle_kind": "batch",
            "service_ports": [],
            "checkpoint_policy": "app_managed",
            "runtime_profile": {"restartable": True},
        }
        self.store.allocations.append(
            {
                "allocation_id": "alloc-preempting",
                "job_id": "job-preempting",
                "node_id": "node-a",
                "status": "releasing",
                "execution_backend": "http_agent",
                "runtime_job_handle": "handle-job-preempting",
            }
        )
        self.fake_main.app_state.cluster_control = ClusterControlPlaneService(
            self.store,
            ClusterSchedulerCore(),
            _FakeControlPlane(self.store),
        )

        with mock.patch.dict(sys.modules, {"app.main": self.fake_main}):
            response = self.client.get("/api/cluster/jobs")

        self.assertEqual(response.status_code, 200)
        job = response.json()["jobs"][0]
        self.assertEqual(job["runtime_job_handle"], "handle-job-preempting")
        self.assertEqual(job["has_releasing_allocation"], True)

    def test_cluster_job_runtime_control_routes(self):
        with mock.patch.dict(sys.modules, {"app.main": self.fake_main}):
            self.client.post(
                "/api/cluster/jobs",
                json={
                    "job_id": "job-ctl-1",
                    "tenant_id": "tenant-a",
                    "project_id": "project-a",
                    "queue_id": "default",
                    "submitter_id": "alice",
                    "job_type": "batch",
                    "entrypoint": "python train.py",
                    "args": [],
                    "env": {},
                    "resource_request": {"gpu": 1},
                    "placement_constraints": {},
                    "priority": 50,
                    "preemptible": True,
                    "max_retries": 1,
                    "timeout_seconds": 600,
                    "checkpoint_policy": "app_managed",
                },
            )
            paused = self.client.post("/api/cluster/jobs/job-ctl-1/pause")
            resumed = self.client.post("/api/cluster/jobs/job-ctl-1/resume")
            checkpointed = self.client.post(
                "/api/cluster/jobs/job-ctl-1/checkpoint",
                json={"timeout_seconds": 15},
            )
            restored = self.client.post(
                "/api/cluster/jobs/job-ctl-1/restore",
                json={"checkpoint_id": "ckpt-job-1"},
            )

        self.assertEqual(paused.status_code, 200)
        self.assertEqual(paused.json()["status"], "paused")
        self.assertEqual(resumed.status_code, 200)
        self.assertEqual(resumed.json()["status"], "running")
        self.assertEqual(checkpointed.status_code, 200)
        self.assertEqual(checkpointed.json()["checkpoint_status"], "checkpoint_requested")
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(restored.json()["status"], "restoring")


if __name__ == "__main__":
    unittest.main()
