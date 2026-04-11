from __future__ import annotations

import json
import os
import socket
import subprocess
import tempfile
import time

import psutil

from runtime_store import RuntimeStore


DEFAULT_RUNTIME_ROOT = os.path.join(tempfile.gettempdir(), "ai-datacenter-runtime")


class JobRuntime:
    def __init__(self, store: RuntimeStore, process_launcher=None, runtime_root: str = ""):
        self.store = store
        self._process_launcher = process_launcher or subprocess.Popen
        self._processes: dict[str, subprocess.Popen] = {}
        self._runtime_root = runtime_root or DEFAULT_RUNTIME_ROOT

    def launch(self, payload: dict) -> dict:
        return self._start_process(payload, state="running", restore_from="")

    def restore(self, payload: dict) -> dict:
        return self._start_process(
            payload,
            state="restoring",
            restore_from=str(payload.get("manifest_path") or ""),
        )

    def list_jobs(self) -> list[dict]:
        self._reap_finished_processes()
        self._refresh_runtime_state()
        return self.store.list_jobs()

    def get_job(self, job_handle: str) -> dict | None:
        self._reap_finished_processes()
        self._refresh_runtime_state()
        return self.store.get_job(job_handle)

    def get_checkpoint(self, job_handle: str) -> dict | None:
        item = self.get_job(job_handle)
        if item is None:
            return None
        return {
            "job_handle": str(item["job_handle"]),
            "job_id": str(item["job_id"]),
            "checkpoint_id": str(item.get("checkpoint_id") or ""),
            "checkpoint_state": str(item.get("checkpoint_state") or ""),
            "checkpoint_manifest_path": str(item.get("checkpoint_manifest_path") or ""),
            "checkpoint_error": str(item.get("checkpoint_error") or ""),
        }

    def terminate(self, job_handle: str) -> dict | None:
        self._reap_finished_processes()
        process = self._processes.get(job_handle)
        if process is None:
            return self.store.get_job(job_handle)
        return self._finalize_process(job_handle, process, forced_state="canceled")

    def pause(self, job_handle: str) -> dict | None:
        return self._change_pause_state(job_handle, pause=True)

    def resume(self, job_handle: str) -> dict | None:
        return self._change_pause_state(job_handle, pause=False)

    def request_checkpoint(self, job_handle: str, payload: dict) -> dict | None:
        item = self.get_job(job_handle)
        if item is None:
            return None
        if str(item.get("checkpoint_policy") or "") != "app_managed":
            raise ValueError("runtime job does not support app-managed checkpoint")
        checkpoint_id = str(payload["checkpoint_id"])
        self._write_json(
            self._checkpoint_request_path(item),
            {
                "checkpoint_id": checkpoint_id,
                "artifact_root": str(item.get("artifact_root") or ""),
                "timeout_seconds": int(payload.get("timeout_seconds") or 30),
                "requested_at": time.time(),
                "reason": str(payload.get("reason") or ""),
            },
        )
        return self.store.update_job_checkpoint(
            job_handle,
            checkpoint_id=checkpoint_id,
            checkpoint_state="checkpoint_requested",
            checkpoint_manifest_path="",
            checkpoint_error="",
        )

    def _build_env(
        self,
        overrides: dict | None,
        *,
        job_handle: str,
        job_id: str,
        control_dir: str,
        artifact_root: str,
        restore_from: str,
    ) -> dict[str, str]:
        env = dict(os.environ)
        env.update({str(key): str(value) for key, value in (overrides or {}).items()})
        env["AIDC_JOB_HANDLE"] = job_handle
        env["AIDC_JOB_ID"] = job_id
        env["AIDC_CONTROL_DIR"] = control_dir
        env["AIDC_ARTIFACT_ROOT"] = artifact_root
        if restore_from:
            env["AIDC_RESTORE_FROM"] = restore_from
        return env

    def shutdown(self) -> None:
        for job_handle, process in list(self._processes.items()):
            self._wait_for_process(job_handle, process)

    def _start_process(self, payload: dict, *, state: str, restore_from: str) -> dict:
        self._reap_finished_processes()
        job_handle = str(payload["job_handle"])
        runtime_paths = self._runtime_paths(job_handle)
        process = self._process_launcher(
            list(payload["command"]),
            cwd=payload.get("working_dir") or None,
            env=self._build_env(
                payload.get("env"),
                job_handle=job_handle,
                job_id=str(payload["job_id"]),
                control_dir=runtime_paths["control_dir"],
                artifact_root=runtime_paths["artifact_root"],
                restore_from=restore_from,
            ),
        )
        self._processes[job_handle] = process
        record = self._build_record(
            job_handle,
            payload,
            int(process.pid),
            state=state,
            control_dir=runtime_paths["control_dir"],
            artifact_root=runtime_paths["artifact_root"],
            restore_from=restore_from,
        )
        return self.store.save_job(record)

    def _build_record(
        self,
        job_handle: str,
        payload: dict,
        pid: int,
        *,
        state: str,
        control_dir: str,
        artifact_root: str,
        restore_from: str,
    ) -> dict:
        service_ports = self._service_ports(payload.get("service_ports"))
        created_at = time.time()
        readiness_state = self._initial_readiness_state(state, service_ports)
        return {
            "job_handle": job_handle,
            "job_id": str(payload["job_id"]),
            "reservation_id": str(payload["reservation_id"]),
            "pid": pid,
            "state": state,
            "exit_code": None,
            "last_error": "",
            "command": list(payload["command"]),
            "task_kind": str(payload.get("task_kind") or "batch_compute"),
            "lifecycle_kind": str(payload.get("lifecycle_kind") or "batch"),
            "service_ports": service_ports,
            "checkpoint_policy": str(payload.get("checkpoint_policy") or "none"),
            "runtime_profile": dict(payload.get("runtime_profile", {})),
            "health_state": readiness_state,
            "readiness_state": readiness_state,
            "control_dir": control_dir,
            "artifact_root": artifact_root,
            "restore_from": restore_from,
            "checkpoint_state": "",
            "checkpoint_id": "",
            "checkpoint_manifest_path": "",
            "checkpoint_error": "",
            "paused_at": None,
            "resumed_at": None,
            "created_at": created_at,
            "started_at": created_at,
            "finished_at": None,
        }

    def _service_ports(self, value) -> list[int]:
        return [int(item) for item in (value or [])]

    def _initial_readiness_state(self, state: str, service_ports: list[int]) -> str:
        if state == "restoring":
            return "restoring"
        if service_ports:
            return "starting"
        return state

    def _refresh_runtime_state(self) -> None:
        for item in self.store.list_jobs():
            self._refresh_checkpoint_state(item)
            self._refresh_restore_state(item)
            self._refresh_readiness_state(item)

    def _reap_finished_processes(self) -> None:
        for job_handle, process in list(self._processes.items()):
            if process.poll() is None:
                continue
            self._finalize_process(job_handle, process)

    def _refresh_checkpoint_state(self, item: dict) -> None:
        checkpoint_state = str(item.get("checkpoint_state") or "")
        if checkpoint_state not in {"checkpoint_requested", "checkpointing"}:
            return
        result = self._read_json(self._checkpoint_result_path(item))
        if result is None:
            return
        status = str(result.get("status") or "")
        if status == "ready":
            self.store.update_job_checkpoint(
                str(item["job_handle"]),
                checkpoint_state="checkpoint_ready",
                checkpoint_manifest_path=str(result.get("manifest_path") or ""),
                checkpoint_error="",
            )
            return
        if status == "failed":
            self.store.update_job_checkpoint(
                str(item["job_handle"]),
                checkpoint_state="checkpoint_failed",
                checkpoint_manifest_path="",
                checkpoint_error=str(result.get("error") or "checkpoint failed"),
            )

    def _refresh_restore_state(self, item: dict) -> None:
        if str(item.get("state") or "") != "restoring":
            return
        service_ports = item.get("service_ports") or []
        if service_ports:
            return
        self.store.update_job_fields(
            str(item["job_handle"]),
            state="running",
            readiness_state="running",
            health_state="running",
        )

    def _refresh_readiness_state(self, item: dict) -> None:
        state = str(item.get("state") or "")
        if state not in {"running", "restoring"}:
            return
        service_ports = item.get("service_ports") or []
        if not service_ports:
            return
        if not self._ports_ready(service_ports):
            return
        self.store.update_job_fields(
            str(item["job_handle"]),
            state="ready",
            readiness_state="ready",
            health_state="ready",
        )

    def _ports_ready(self, ports: list[int]) -> bool:
        return all(self._port_ready(port) for port in ports)

    def _port_ready(self, port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", int(port)), timeout=0.05):
                return True
        except OSError:
            return False

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

    def _finalize_process(
        self,
        job_handle: str,
        process: subprocess.Popen,
        *,
        forced_state: str | None = None,
    ) -> dict:
        exit_code = self._wait_for_exit(job_handle, process)
        state = forced_state or self._state_from_exit_code(exit_code)
        last_error = self._last_error_for_state(state, exit_code)
        return self.store.update_job_terminal(
            job_handle,
            state=state,
            exit_code=exit_code,
            last_error=last_error,
        )

    def _wait_for_exit(self, job_handle: str, process: subprocess.Popen) -> int | None:
        self._wait_for_process(job_handle, process)
        return process.returncode

    def _state_from_exit_code(self, exit_code: int | None) -> str:
        return "succeeded" if exit_code == 0 else "failed"

    def _last_error_for_state(self, state: str, exit_code: int | None) -> str:
        if state != "failed":
            return ""
        return f"runtime exited with code {exit_code}"

    def _change_pause_state(self, job_handle: str, *, pause: bool) -> dict | None:
        self._reap_finished_processes()
        process = self._processes.get(job_handle)
        if process is None:
            return self.store.get_job(job_handle)
        item = self.store.get_job(job_handle)
        if item is None:
            return None
        current_state = str(item.get("state") or "")
        expected = {"running", "ready"} if pause else {"paused"}
        if current_state not in expected:
            action = "pause" if pause else "resume"
            raise ValueError(f"runtime job cannot {action} from {current_state}")
        controller = psutil.Process(process.pid)
        if pause:
            controller.suspend()
            return self.store.update_job_pause_state(
                job_handle,
                state="paused",
                readiness_state="paused",
                health_state="paused",
                timestamp=time.time(),
            )
        controller.resume()
        service_ports = item.get("service_ports") or []
        next_state = "ready" if service_ports and self._ports_ready(service_ports) else "running"
        return self.store.update_job_pause_state(
            job_handle,
            state=next_state,
            readiness_state=next_state,
            health_state=next_state,
            timestamp=time.time(),
        )

    def _runtime_paths(self, job_handle: str) -> dict[str, str]:
        root = os.path.join(self._runtime_root, job_handle)
        control_dir = os.path.join(root, "control")
        artifact_root = os.path.join(root, "artifacts")
        os.makedirs(control_dir, exist_ok=True)
        os.makedirs(artifact_root, exist_ok=True)
        return {"root": root, "control_dir": control_dir, "artifact_root": artifact_root}

    def _checkpoint_request_path(self, item: dict) -> str:
        return os.path.join(str(item["control_dir"]), "checkpoint-request.json")

    def _checkpoint_result_path(self, item: dict) -> str:
        return os.path.join(str(item["control_dir"]), "checkpoint-result.json")

    def _write_json(self, path: str, payload: dict) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)

    def _read_json(self, path: str) -> dict | None:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as handle:
            return dict(json.load(handle))
