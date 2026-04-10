import os
import sys
import unittest

from fastapi.testclient import TestClient


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "server-agent"))

from main import app  # noqa: E402


SLEEP_COMMAND = [sys.executable, "-c", "import time; time.sleep(0.2)"]


class NodeRuntimeApiTests(unittest.TestCase):
    def test_create_reservation_and_launch_job(self):
        client = TestClient(app)
        reservation = client.post(
            "/api/runtime/reservations",
            json={
                "reservation_id": "res-1",
                "job_id": "job-1",
                "gpu_indexes": [0],
                "cpu_cores": [0, 1],
            },
        )
        launch = client.post(
            "/api/runtime/jobs/launch",
            json={
                "job_handle": "handle-1",
                "job_id": "job-1",
                "reservation_id": "res-1",
                "command": SLEEP_COMMAND,
                "env": {},
            },
        )

        self.assertEqual(reservation.status_code, 200)
        self.assertEqual(launch.status_code, 200)
        self.assertEqual(launch.json()["state"], "running")

    def test_launch_rejects_unknown_reservation(self):
        client = TestClient(app)
        launch = client.post(
            "/api/runtime/jobs/launch",
            json={
                "job_handle": "handle-missing",
                "job_id": "job-2",
                "reservation_id": "missing",
                "command": SLEEP_COMMAND,
                "env": {},
            },
        )

        self.assertEqual(launch.status_code, 404)


if __name__ == "__main__":
    unittest.main()
