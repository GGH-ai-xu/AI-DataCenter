import os
import sys
import tempfile
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.cluster_control.checkpoint_sqlite_support import (  # noqa: E402
    ensure_cluster_checkpoint_tables,
)
from app.services.cluster_control.control_plane_job_actions import (  # noqa: E402
    restore_checkpointed_job,
)
from app.services.cluster_control.models import JobSpecRecord  # noqa: E402
from app.services.cluster_control.runtime_feedback import (  # noqa: E402
    sync_runtime_job_state,
)
from app.services.data_store import DataStore  # noqa: E402


def _build_job(**overrides):
    payload = {
        "job_id": "job-ckpt",
        "tenant_id": "tenant-a",
        "project_id": "project-a",
        "queue_id": "default",
        "submitter_id": "alice",
        "job_type": "batch",
        "entrypoint": "python train.py",
        "args": (),
        "env": {},
        "resource_request": {"gpu": 1},
        "placement_constraints": {},
        "priority": 50,
        "preemptible": True,
        "max_retries": 1,
        "timeout_seconds": 600,
        "checkpoint_policy": "app_managed",
    }
    payload.update(overrides)
    return JobSpecRecord(**payload)


class _RestoreStore:
    def __init__(self):
        self.jobs = {
            "job-restore": {
                "job_id": "job-restore",
                "status": "paused",
                "entrypoint": "python train.py",
                "args": [],
                "env": {},
                "task_kind": "batch_compute",
                "lifecycle_kind": "batch",
                "service_ports": [],
                "checkpoint_policy": "app_managed",
                "runtime_profile": {},
                "checkpoint_id": "",
                "checkpoint_manifest_path": "",
            }
        }
        self.allocations = [
            {
                "allocation_id": "alloc-restore",
                "job_id": "job-restore",
                "reservation_id": "res-restore",
                "node_id": "node-a",
                "runtime_job_handle": "handle-restore",
                "status": "paused",
                "execution_backend": "http_agent",
            }
        ]
        self.nodes = {
            "node-a": {
                "node_id": "node-a",
                "execution_backend": "http_agent",
                "base_url": "http://127.0.0.1:8001",
            }
        }
        self.checkpoints = [
            {
                "checkpoint_id": "ckpt-old",
                "job_id": "job-restore",
                "status": "checkpoint_ready",
                "manifest_path": "/tmp/ckpt-old.json",
                "updated_at": 10.0,
            },
            {
                "checkpoint_id": "ckpt-new",
                "job_id": "job-restore",
                "status": "checkpoint_ready",
                "manifest_path": "/tmp/ckpt-new.json",
                "updated_at": 20.0,
            },
        ]
        self.allocation_updates = []

    async def get_cluster_job(self, job_id):
        item = self.jobs.get(job_id)
        return dict(item) if item is not None else None

    async def list_cluster_allocations(self):
        return [dict(item) for item in self.allocations]

    async def get_cluster_node(self, node_id):
        item = self.nodes.get(node_id)
        return dict(item) if item is not None else None

    async def update_cluster_job_state(self, job_id, status, *, execution_backend=""):
        self.jobs[job_id]["status"] = status
        self.jobs[job_id]["execution_backend"] = execution_backend

    async def update_cluster_allocations_for_job(self, job_id, status):
        self.allocation_updates.append((job_id, status))
        for item in self.allocations:
            if item["job_id"] == job_id:
                item["status"] = status

    async def get_cluster_checkpoint(self, checkpoint_id):
        for item in self.checkpoints:
            if item["checkpoint_id"] == checkpoint_id:
                return dict(item)
        return None

    async def get_latest_ready_cluster_checkpoint(self, job_id):
        ready = [
            dict(item)
            for item in self.checkpoints
            if item["job_id"] == job_id and item["status"] == "checkpoint_ready"
        ]
        ready.sort(key=lambda item: float(item["updated_at"]), reverse=True)
        return ready[0] if ready else None


class _RestoreOrchestrator:
    def __init__(self):
        self.restore_payloads = []

    async def restore_runtime_job(self, node, payload):
        self.restore_payloads.append({"node": dict(node), "payload": dict(payload)})
        return {
            "job_handle": str(payload["job_handle"]),
            "checkpoint_id": str(payload["checkpoint_id"]),
            "state": "restoring",
        }


class ClusterCheckpointHistoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_ensure_cluster_checkpoint_tables_backfills_job_checkpoint_pointer(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = DataStore(os.path.join(tmpdir, "cluster.db"))
            await store.init()
            try:
                await store.create_cluster_job(_build_job(job_id="job-backfill"))
                await store.update_cluster_job_checkpoint(
                    "job-backfill",
                    checkpoint_id="ckpt-backfill",
                    checkpoint_status="checkpoint_ready",
                    checkpoint_manifest_path="/tmp/ckpt-backfill.json",
                    checkpoint_error="",
                    checkpoint_updated_at=42.0,
                )
                await store._db.execute("DELETE FROM cluster_checkpoints")
                await store._db.commit()

                await ensure_cluster_checkpoint_tables(store._db)
                checkpoints = await store.list_cluster_checkpoints(job_id="job-backfill")
            finally:
                await store.close()

        self.assertEqual(len(checkpoints), 1)
        self.assertEqual(checkpoints[0]["checkpoint_id"], "ckpt-backfill")
        self.assertEqual(checkpoints[0]["manifest_path"], "/tmp/ckpt-backfill.json")
        self.assertEqual(checkpoints[0]["status"], "checkpoint_ready")

    async def test_sync_runtime_job_state_persists_checkpoint_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = DataStore(os.path.join(tmpdir, "cluster.db"))
            await store.init()
            try:
                await store.create_cluster_job(_build_job(job_id="job-runtime"))
                allocation = {
                    "allocation_id": "alloc-runtime",
                    "job_id": "job-runtime",
                    "reservation_id": "res-runtime",
                    "node_id": "node-a",
                    "gpu_bindings_json": "[\"gpu-0\"]",
                    "runtime_job_handle": "handle-runtime",
                    "status": "active",
                    "execution_backend": "http_agent",
                }
                await store.create_cluster_allocation(allocation)

                await sync_runtime_job_state(
                    store,
                    allocation,
                    {
                        "job_handle": "handle-runtime",
                        "checkpoint_id": "ckpt-runtime",
                        "checkpoint_state": "checkpoint_ready",
                        "checkpoint_manifest_path": "/tmp/ckpt-runtime.json",
                        "checkpoint_error": "",
                        "finished_at": 88.0,
                    },
                )
                job = await store.get_cluster_job("job-runtime")
                checkpoints = await store.list_cluster_checkpoints(job_id="job-runtime")
            finally:
                await store.close()

        self.assertEqual(job["checkpoint_id"], "ckpt-runtime")
        self.assertEqual(job["checkpoint_status"], "checkpoint_ready")
        self.assertEqual(len(checkpoints), 1)
        self.assertEqual(checkpoints[0]["allocation_id"], "alloc-runtime")
        self.assertEqual(checkpoints[0]["node_id"], "node-a")
        self.assertEqual(checkpoints[0]["runtime_job_handle"], "handle-runtime")

    async def test_restore_checkpointed_job_uses_latest_ready_history_when_unspecified(self):
        store = _RestoreStore()
        orchestrator = _RestoreOrchestrator()
        job = await store.get_cluster_job("job-restore")

        updated = await restore_checkpointed_job(
            store,
            orchestrator,
            store.get_cluster_job,
            job,
            checkpoint_id="",
        )

        self.assertEqual(updated["status"], "restoring")
        self.assertEqual(store.allocation_updates, [("job-restore", "active")])
        self.assertEqual(
            orchestrator.restore_payloads[0]["payload"]["checkpoint_id"],
            "ckpt-new",
        )
        self.assertEqual(
            orchestrator.restore_payloads[0]["payload"]["manifest_path"],
            "/tmp/ckpt-new.json",
        )


if __name__ == "__main__":
    unittest.main()
