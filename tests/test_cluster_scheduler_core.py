import os
import sys
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.cluster_control.control_plane import (  # noqa: E402
    ClusterControlPlaneService,
)
from app.services.cluster_control.models import JobSpecRecord  # noqa: E402
from app.services.cluster_control.scheduler_core import ClusterSchedulerCore  # noqa: E402


class _FakeStore:
    def __init__(self):
        self.created_jobs = []

    async def create_cluster_job(self, record):
        self.created_jobs.append(record)


class _FakeOrchestrator:
    def __init__(self):
        self.calls = []

    async def dispatch_plan(self, job_record, plan, **kwargs):
        self.calls.append((job_record, plan, kwargs))


class ClusterSchedulerCoreTests(unittest.TestCase):
    def test_selects_best_fit_schedulable_node_with_sufficient_capacity(self):
        scheduler = ClusterSchedulerCore()
        job = JobSpecRecord(
            job_id="job-1",
            tenant_id="tenant-a",
            project_id="project-a",
            queue_id="default",
            submitter_id="alice",
            job_type="batch",
            entrypoint="python train.py",
            args=(),
            env={},
            resource_request={"gpu": 1, "cpu": 4},
            placement_constraints={},
            priority=50,
            preemptible=True,
            max_retries=1,
            timeout_seconds=600,
        )

        plan = scheduler.plan_job(
            job,
            nodes=[
                {"node_id": "node-a", "schedulable": True, "gpu_free": 1, "cpu_free": 16},
                {"node_id": "node-b", "schedulable": True, "gpu_free": 4, "cpu_free": 64},
            ],
        )

        self.assertEqual(plan.plan_type, "placement")
        self.assertEqual(plan.selected_node, "node-a")
        self.assertEqual(plan.selected_devices, ("gpu-0",))

    def test_returns_queue_wait_plan_when_no_node_matches(self):
        scheduler = ClusterSchedulerCore()
        job = JobSpecRecord(
            job_id="job-2",
            tenant_id="tenant-a",
            project_id="project-a",
            queue_id="default",
            submitter_id="alice",
            job_type="batch",
            entrypoint="python train.py",
            args=(),
            env={},
            resource_request={"gpu": 2},
            placement_constraints={},
            priority=50,
            preemptible=True,
            max_retries=1,
            timeout_seconds=600,
        )

        plan = scheduler.plan_job(
            job,
            nodes=[{"node_id": "node-a", "schedulable": True, "gpu_free": 1}],
        )

        self.assertEqual(plan.plan_type, "queue_wait")
        self.assertEqual(plan.selected_node, "")


class ClusterControlPlaneServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_submit_job_persists_record_and_dispatches_placement_plan(self):
        store = _FakeStore()
        orchestrator = _FakeOrchestrator()
        scheduler = ClusterSchedulerCore()
        service = ClusterControlPlaneService(store, scheduler, orchestrator)
        job = JobSpecRecord(
            job_id="job-3",
            tenant_id="tenant-a",
            project_id="project-a",
            queue_id="default",
            submitter_id="alice",
            job_type="batch",
            entrypoint="python train.py",
            args=(),
            env={},
            resource_request={"gpu": 1},
            placement_constraints={},
            priority=50,
            preemptible=True,
            max_retries=1,
            timeout_seconds=600,
        )

        plan = await service.submit_job(
            job,
            nodes=[{"node_id": "node-a", "schedulable": True, "gpu_free": 1}],
        )

        self.assertEqual(store.created_jobs[0].job_id, "job-3")
        self.assertEqual(plan.plan_type, "placement")
        self.assertEqual(orchestrator.calls[0][1].selected_node, "node-a")


if __name__ == "__main__":
    unittest.main()
