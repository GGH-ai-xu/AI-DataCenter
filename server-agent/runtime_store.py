from __future__ import annotations

from threading import Lock


class RuntimeStore:
    def __init__(self):
        self._reservations: dict[str, dict] = {}
        self._jobs: dict[str, dict] = {}
        self._lock = Lock()

    def create_reservation(self, payload: dict) -> dict:
        item = {
            "reservation_id": str(payload["reservation_id"]),
            "job_id": str(payload["job_id"]),
            "gpu_indexes": list(payload.get("gpu_indexes", [])),
            "cpu_cores": list(payload.get("cpu_cores", [])),
        }
        with self._lock:
            self._reservations[item["reservation_id"]] = item
        return dict(item)

    def get_reservation(self, reservation_id: str) -> dict | None:
        with self._lock:
            item = self._reservations.get(reservation_id)
        return dict(item) if item is not None else None

    def save_job(self, payload: dict) -> dict:
        item = dict(payload)
        with self._lock:
            self._jobs[item["job_handle"]] = item
        return dict(item)

    def get_job(self, job_handle: str) -> dict | None:
        with self._lock:
            item = self._jobs.get(job_handle)
        return dict(item) if item is not None else None
