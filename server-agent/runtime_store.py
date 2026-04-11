from __future__ import annotations

import time
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

    def reset(self) -> None:
        with self._lock:
            self._reservations = {}
            self._jobs = {}

    def save_job(self, payload: dict) -> dict:
        item = dict(payload)
        with self._lock:
            self._jobs[item["job_handle"]] = item
        return dict(item)

    def get_job(self, job_handle: str) -> dict | None:
        with self._lock:
            item = self._jobs.get(job_handle)
        return dict(item) if item is not None else None

    def list_jobs(self) -> list[dict]:
        with self._lock:
            jobs = [dict(item) for item in self._jobs.values()]
        return sorted(jobs, key=lambda item: float(item.get("created_at") or 0), reverse=True)

    def update_job_fields(self, job_handle: str, **changes) -> dict:
        with self._lock:
            item = dict(self._jobs.get(job_handle) or {})
            if not item:
                raise KeyError(job_handle)
            item.update(changes)
            self._jobs[job_handle] = item
        return dict(item)

    def update_job_pause_state(
        self,
        job_handle: str,
        *,
        state: str,
        readiness_state: str,
        health_state: str,
        timestamp: float,
    ) -> dict:
        field_name = "paused_at" if state == "paused" else "resumed_at"
        return self.update_job_fields(
            job_handle,
            state=state,
            readiness_state=readiness_state,
            health_state=health_state,
            **{field_name: timestamp},
        )

    def update_job_checkpoint(self, job_handle: str, **changes) -> dict:
        return self.update_job_fields(job_handle, **changes)

    def update_job_terminal(
        self,
        job_handle: str,
        *,
        state: str,
        exit_code: int | None,
        last_error: str,
    ) -> dict:
        with self._lock:
            item = dict(self._jobs.get(job_handle) or {})
            if not item:
                raise KeyError(job_handle)
            item["state"] = state
            item["exit_code"] = exit_code
            item["last_error"] = last_error
            item["readiness_state"] = state
            item["health_state"] = "terminated" if state == "canceled" else state
            item["finished_at"] = time.time()
            self._jobs[job_handle] = item
        return dict(item)
