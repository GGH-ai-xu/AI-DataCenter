import os
import socket
import sys
import time
import unittest

from fastapi.testclient import TestClient


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "server-agent"))

from main import app  # noqa: E402


SLEEP_COMMAND = [sys.executable, "-c", "import time; time.sleep(0.2)"]
COMPLETE_COMMAND = [sys.executable, "-c", "print('done')"]


def _find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _http_service_command(port):
    return [
        sys.executable,
        "-m",
        "http.server",
        str(port),
        "--bind",
        "127.0.0.1",
    ]


class NodeRuntimeApiTests(unittest.TestCase):
    def test_create_reservation_and_launch_job(self):
        with TestClient(app) as client:
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
        with TestClient(app) as client:
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

    def test_service_runtime_job_reports_ready_state_and_task_metadata(self):
        port = _find_free_port()

        with TestClient(app) as client:
            reservation = client.post(
                "/api/runtime/reservations",
                json={
                    "reservation_id": "res-service",
                    "job_id": "job-service",
                    "gpu_indexes": [0],
                    "cpu_cores": [],
                },
            )
            launch = client.post(
                "/api/runtime/jobs/launch",
                json={
                    "job_handle": "handle-service",
                    "job_id": "job-service",
                    "reservation_id": "res-service",
                    "command": _http_service_command(port),
                    "env": {},
                    "task_kind": "inference_service",
                    "lifecycle_kind": "service",
                    "service_ports": [port],
                    "runtime_profile": {
                        "latency_sensitive": True,
                        "restartable": False,
                        "exclusive_gpu": True,
                        "expected_duration_seconds": 0,
                    },
                },
            )
            deadline = time.time() + 2
            item = None
            while time.time() < deadline:
                response = client.get("/api/runtime/jobs")
                item = next(
                    job
                    for job in response.json()["jobs"]
                    if job["job_handle"] == "handle-service"
                )
                if item.get("state") == "ready":
                    break
                time.sleep(0.05)
            client.post("/api/runtime/jobs/handle-service/terminate")

        self.assertEqual(reservation.status_code, 200)
        self.assertEqual(launch.status_code, 200)
        self.assertEqual(item.get("task_kind"), "inference_service")
        self.assertEqual(item.get("lifecycle_kind"), "service")
        self.assertEqual(item.get("service_ports"), [port])
        self.assertEqual(item.get("readiness_state"), "ready")
        self.assertEqual(item.get("state"), "ready")
        self.assertEqual(
            (item.get("runtime_profile") or {}).get("latency_sensitive"),
            True,
        )

    def test_list_runtime_jobs_reaps_finished_process(self):
        with TestClient(app) as client:
            client.post(
                "/api/runtime/reservations",
                json={
                    "reservation_id": "res-finished",
                    "job_id": "job-finished",
                    "gpu_indexes": [0],
                    "cpu_cores": [],
                },
            )
            client.post(
                "/api/runtime/jobs/launch",
                json={
                    "job_handle": "handle-finished",
                    "job_id": "job-finished",
                    "reservation_id": "res-finished",
                    "command": COMPLETE_COMMAND,
                    "env": {},
                },
            )
            deadline = time.time() + 1
            item = None
            while time.time() < deadline:
                response = client.get("/api/runtime/jobs")
                item = next(job for job in response.json()["jobs"] if job["job_handle"] == "handle-finished")
                if item["state"] != "running":
                    break
                time.sleep(0.02)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(item["state"], "succeeded")
        self.assertEqual(item["exit_code"], 0)

    def test_terminate_runtime_job_by_handle(self):
        with TestClient(app) as client:
            client.post(
                "/api/runtime/reservations",
                json={
                    "reservation_id": "res-cancel",
                    "job_id": "job-cancel",
                    "gpu_indexes": [0],
                    "cpu_cores": [],
                },
            )
            client.post(
                "/api/runtime/jobs/launch",
                json={
                    "job_handle": "handle-cancel",
                    "job_id": "job-cancel",
                    "reservation_id": "res-cancel",
                    "command": SLEEP_COMMAND,
                    "env": {},
                },
            )
            response = client.post("/api/runtime/jobs/handle-cancel/terminate")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "canceled")

    def test_pause_and_resume_runtime_job_by_handle(self):
        with TestClient(app) as client:
            client.post(
                "/api/runtime/reservations",
                json={
                    "reservation_id": "res-pause",
                    "job_id": "job-pause",
                    "gpu_indexes": [0],
                    "cpu_cores": [],
                },
            )
            client.post(
                "/api/runtime/jobs/launch",
                json={
                    "job_handle": "handle-pause",
                    "job_id": "job-pause",
                    "reservation_id": "res-pause",
                    "command": SLEEP_COMMAND,
                    "env": {},
                },
            )

            paused = client.post("/api/runtime/jobs/handle-pause/pause")
            resumed = client.post("/api/runtime/jobs/handle-pause/resume")

        self.assertEqual(paused.status_code, 200)
        self.assertEqual(paused.json()["state"], "paused")
        self.assertEqual(resumed.status_code, 200)
        self.assertEqual(resumed.json()["state"], "running")

    def test_checkpoint_request_creates_pending_checkpoint_state(self):
        with TestClient(app) as client:
            client.post(
                "/api/runtime/reservations",
                json={
                    "reservation_id": "res-ckpt",
                    "job_id": "job-ckpt",
                    "gpu_indexes": [0],
                    "cpu_cores": [],
                },
            )
            client.post(
                "/api/runtime/jobs/launch",
                json={
                    "job_handle": "handle-ckpt",
                    "job_id": "job-ckpt",
                    "reservation_id": "res-ckpt",
                    "command": SLEEP_COMMAND,
                    "env": {},
                    "checkpoint_policy": "app_managed",
                },
            )

            response = client.post(
                "/api/runtime/jobs/handle-ckpt/checkpoint",
                json={"checkpoint_id": "ckpt-1", "timeout_seconds": 15},
            )
            details = client.get("/api/runtime/jobs/handle-ckpt/checkpoint")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["checkpoint_state"], "checkpoint_requested")
        self.assertEqual(details.status_code, 200)
        self.assertEqual(details.json()["checkpoint_id"], "ckpt-1")

    def test_restore_runtime_job_uses_manifest_env(self):
        with TestClient(app) as client:
            client.post(
                "/api/runtime/reservations",
                json={
                    "reservation_id": "res-restore",
                    "job_id": "job-restore",
                    "gpu_indexes": [0],
                    "cpu_cores": [],
                },
            )
            restore = client.post(
                "/api/runtime/jobs/handle-restore/restore",
                json={
                    "job_handle": "handle-restore",
                    "job_id": "job-restore",
                    "reservation_id": "res-restore",
                    "checkpoint_id": "ckpt-restore",
                    "manifest_path": "C:/tmp/aidc/ckpt.json",
                    "command": COMPLETE_COMMAND,
                    "env": {},
                },
            )

        self.assertEqual(restore.status_code, 200)
        self.assertEqual(restore.json()["state"], "restoring")


if __name__ == "__main__":
    unittest.main()
