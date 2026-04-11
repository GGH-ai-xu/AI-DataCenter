import os
import sys
import tempfile
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.data_store import DataStore  # noqa: E402
from app.services.cluster_control.models import JobSpecRecord, PlacementPlan  # noqa: E402


class ClusterControlModelTests(unittest.IsolatedAsyncioTestCase):
    async def test_data_store_persists_queue_job_and_allocation_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = DataStore(os.path.join(tmpdir, "cluster.db"))
            await store.init()
            try:
                await store.upsert_cluster_queue(
                    {
                        "queue_id": "default",
                        "name": "Default",
                        "state": "active",
                        "default_priority": 50,
                    }
                )
                await store.create_cluster_job(
                    JobSpecRecord(
                        job_id="job-1",
                        tenant_id="tenant-a",
                        project_id="project-a",
                        queue_id="default",
                        submitter_id="alice",
                        job_type="batch",
                        entrypoint="python train.py",
                        args=("--epochs", "1"),
                        env={"CUDA_VISIBLE_DEVICES": "0"},
                        resource_request={
                            "gpu": 1,
                            "cpu": 4,
                            "memory_bytes": 8 * 1024**3,
                        },
                        placement_constraints={},
                        priority=50,
                        preemptible=True,
                        max_retries=1,
                        timeout_seconds=3600,
                    )
                )
                await store.create_cluster_allocation(
                    {
                        "allocation_id": "alloc-1",
                        "job_id": "job-1",
                        "node_id": "node-a",
                        "gpu_bindings_json": "[\"gpu-0\"]",
                        "status": "active",
                        "execution_backend": "http_agent",
                    }
                )
                queues = await store.list_cluster_queues()
                job = await store.get_cluster_job("job-1")
                allocations = await store.list_cluster_allocations()
            finally:
                await store.close()

        self.assertEqual(queues[0]["queue_id"], "default")
        self.assertEqual(job["job_id"], "job-1")
        self.assertEqual(allocations[0]["node_id"], "node-a")

    def test_job_spec_record_normalizes_args_and_priority(self):
        record = JobSpecRecord(
            job_id="job-2",
            tenant_id="tenant-a",
            project_id="project-a",
            queue_id="default",
            submitter_id="alice",
            job_type="batch",
            entrypoint="python train.py",
            args=["--epochs", "2"],
            env={},
            resource_request={"gpu": 1},
            placement_constraints={},
            priority="60",
            preemptible=False,
            max_retries=0,
            timeout_seconds=1200,
        )

        self.assertEqual(record.args, ("--epochs", "2"))
        self.assertEqual(record.priority, 60)

    def test_placement_plan_carries_victim_and_action_metadata(self):
        plan = PlacementPlan(
            job_id="job-target",
            plan_type="preempt_then_place",
            selected_node="node-a",
            selected_devices=("gpu-0",),
            score_breakdown={"fit": 1.0},
            victim_job_ids=("job-low",),
            victim_allocation_ids=("alloc-low",),
            followup_job_ids=("job-target",),
            required_actions=(
                {"action": "cancel_job", "job_id": "job-low"},
                {"action": "release_allocation", "allocation_id": "alloc-low"},
            ),
        )

        self.assertEqual(plan.victim_job_ids, ("job-low",))
        self.assertEqual(plan.victim_allocation_ids, ("alloc-low",))
        self.assertEqual(plan.followup_job_ids, ("job-target",))
        self.assertEqual(plan.required_actions[0]["action"], "cancel_job")


if __name__ == "__main__":
    unittest.main()
