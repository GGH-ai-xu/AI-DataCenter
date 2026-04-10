import os
import sys
import types
import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.cluster_control.models import PlacementPlan  # noqa: E402


class _FakeStore:
    def __init__(self):
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

    async def create_cluster_job(self, record):
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
        }

    async def update_cluster_job_state(self, job_id, status, *, execution_backend=""):
        self.jobs[job_id]["status"] = status
        self.jobs[job_id]["execution_backend"] = execution_backend

    async def create_cluster_allocation(self, payload):
        self.allocations.append(dict(payload))

    async def get_cluster_job(self, job_id):
        return self.jobs.get(job_id)

    async def list_cluster_queues(self):
        return list(self.queues)

    async def list_cluster_allocations(self):
        return list(self.allocations)


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


class ClusterJobApiTests(unittest.TestCase):
    def setUp(self):
        from app.api.cluster_jobs import router as jobs_router
        from app.api.cluster_queues import router as queues_router

        self.store = _FakeStore()
        fake_state = types.SimpleNamespace(
            cluster_control=_FakeControlPlane(self.store),
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

    def test_list_queues_and_allocations(self):
        with mock.patch.dict(sys.modules, {"app.main": self.fake_main}):
            queues = self.client.get("/api/cluster/queues")
            allocations = self.client.get("/api/cluster/allocations")

        self.assertEqual(queues.status_code, 200)
        self.assertEqual(queues.json()["queues"][0]["queue_id"], "default")
        self.assertEqual(allocations.status_code, 200)
        self.assertEqual(allocations.json()["allocations"], [])


if __name__ == "__main__":
    unittest.main()
