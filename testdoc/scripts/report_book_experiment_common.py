from __future__ import annotations

import importlib.util
import os
import sys
import time
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVER_AGENT_DIR = ROOT / "server-agent"
BACKEND_DIR = ROOT / "backend"

if str(SERVER_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_AGENT_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.runtime_provider import RuntimeTarget


class FakeConnection:
    def normalize_payload(self, payload: dict) -> RuntimeTarget:
        return RuntimeTarget(
            provider_type=payload["provider_type"],
            label=payload["label"],
            host=payload.get("host"),
            port=payload.get("port"),
            username=payload.get("username"),
            auth_type=payload.get("auth_type"),
            sudo_enabled=bool(payload.get("sudo_enabled")),
            host_fingerprint=payload.get("host_fingerprint"),
        )


class FakeCredentials:
    def save(self, payload: dict) -> str:
        del payload
        return "cred-exp"

    def read(self, credential_id: str) -> dict:
        del credential_id
        return {"password": "secret"}


class FakePrivacy:
    def sanitize_processes(self, processes):
        return list(processes or [])

    def sanitize_training_logs(self, logs):
        return list(logs or [])


class FakeTaskStore:
    def __init__(self, priorities: dict[int, str]):
        self._priorities = priorities
        self.audit_log = []

    async def get_all_task_priorities(self):
        return dict(self._priorities)

    async def save_audit_log(self, **kwargs):
        self.audit_log.append(dict(kwargs))


class FakeProvider:
    def __init__(self, gpus: list[dict], processes: list[dict]):
        self._gpus = [dict(item) for item in gpus]
        self._processes = [dict(item) for item in processes]

    async def get_all_gpus(self):
        return [dict(item) for item in self._gpus]

    async def get_system_info(self):
        return {"cpu_percent": 24.6}

    async def get_processes(self):
        return [dict(item) for item in self._processes]

    async def pause_task(self, pid):
        return {"success": True, "pid": pid}

    async def resume_task(self, pid):
        return {"success": True, "pid": pid}

    async def terminate_task(self, pid):
        return {"success": True, "pid": pid}


class FakeRuntime:
    def __init__(self, gpus: list[dict], provider: FakeProvider):
        self._gpus = [dict(item) for item in gpus]
        self._provider = provider

    async def probe_target(self, target: RuntimeTarget, credentials: dict):
        del target, credentials
        return {
            "status": "connected",
            "health": {"status": "ok"},
            "system": {"cpu_percent": 24.6},
            "gpus": [dict(item) for item in self._gpus],
            "capabilities": {},
        }

    async def switch(self, target: RuntimeTarget, credentials: dict):
        del target, credentials
        return self._provider


def raw_gpus() -> list[dict]:
    return [{"index": index, "name": f"RTX-3090-{index}", "available": True} for index in range(4)]


def raw_processes() -> list[dict]:
    layout = ((0, 3), (1, 2), (2, 3), (3, 3))
    processes = []
    pid = 1001
    for gpu_index, count in layout:
        for offset in range(count):
            processes.append({
                "pid": pid,
                "gpu_index": gpu_index,
                "command": f"train_gpu_{gpu_index}_{offset}.py",
                "priority": "normal",
            })
            pid += 1
    return processes


def load_agent_main_module():
    spec = importlib.util.spec_from_file_location("server_agent_main", SERVER_AGENT_DIR / "main.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def empty_snapshot(gpus: list[dict], processes: list[dict]) -> dict:
    return {
        "collected_at": time.time(),
        "agent_health": {"status": "ok"},
        "runtime": {"status": "connected", "connected": True},
        "import_context": {"valid": False, "imported_gpu_indexes": []},
        "raw": {"system": {"cpu_percent": 24.6}, "gpus": gpus, "processes": processes},
        "scoped": {"system": {"cpu_percent": 24.6}, "gpus": [], "processes": [], "public_processes": []},
    }
