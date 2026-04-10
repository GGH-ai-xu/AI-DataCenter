from __future__ import annotations

import os
import subprocess
import time

from runtime_store import RuntimeStore


class JobRuntime:
    def __init__(self, store: RuntimeStore, process_launcher=None):
        self.store = store
        self._process_launcher = process_launcher or subprocess.Popen
        self._processes: dict[str, subprocess.Popen] = {}

    def launch(self, payload: dict) -> dict:
        self._reap_finished_processes()
        process = self._process_launcher(
            list(payload["command"]),
            cwd=payload.get("working_dir") or None,
            env=self._build_env(payload.get("env")),
        )
        job_handle = str(payload["job_handle"])
        self._processes[job_handle] = process
        record = {
            "job_handle": job_handle,
            "job_id": str(payload["job_id"]),
            "reservation_id": str(payload["reservation_id"]),
            "pid": int(process.pid),
            "state": "running",
            "command": list(payload["command"]),
            "created_at": time.time(),
        }
        return self.store.save_job(record)

    def _build_env(self, overrides: dict | None) -> dict[str, str]:
        env = dict(os.environ)
        env.update({str(key): str(value) for key, value in (overrides or {}).items()})
        return env

    def shutdown(self) -> None:
        for job_handle, process in list(self._processes.items()):
            self._wait_for_process(job_handle, process)

    def _reap_finished_processes(self) -> None:
        for job_handle, process in list(self._processes.items()):
            if process.poll() is None:
                continue
            self._wait_for_process(job_handle, process)

    def _wait_for_process(
        self,
        job_handle: str,
        process: subprocess.Popen,
    ) -> None:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        else:
            process.wait(timeout=2)
        self._processes.pop(job_handle, None)
