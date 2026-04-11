import os
import sys
import types
import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))


class _FakeControlPlane:
    async def list_job_checkpoints(self, job_id):
        if job_id != "job-1":
            raise LookupError(f"cluster job not found: {job_id}")
        return [
            {
                "checkpoint_id": "ckpt-1",
                "job_id": "job-1",
                "status": "checkpoint_ready",
                "manifest_path": "/tmp/ckpt-1.json",
                "error": "",
                "updated_at": 12.0,
            }
        ]

    async def get_checkpoint(self, checkpoint_id):
        if checkpoint_id != "ckpt-1":
            return None
        return {
            "checkpoint_id": "ckpt-1",
            "job_id": "job-1",
            "status": "checkpoint_ready",
            "manifest_path": "/tmp/ckpt-1.json",
            "error": "",
            "updated_at": 12.0,
        }


class ClusterCheckpointApiTests(unittest.TestCase):
    def setUp(self):
        from app.api.cluster_jobs import router

        self.fake_main = types.SimpleNamespace(
            app_state=types.SimpleNamespace(cluster_control=_FakeControlPlane())
        )
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.patch_main = mock.patch.dict(sys.modules, {"app.main": self.fake_main})
        self.patch_main.start()

    def tearDown(self):
        self.client.close()
        self.patch_main.stop()

    def test_lists_job_checkpoints(self):
        response = self.client.get("/api/cluster/jobs/job-1/checkpoints")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["checkpoints"][0]["checkpoint_id"], "ckpt-1")

    def test_gets_checkpoint_by_id(self):
        response = self.client.get("/api/cluster/checkpoints/ckpt-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job_id"], "job-1")


if __name__ == "__main__":
    unittest.main()
