import os
import sys
import tempfile
import types
import unittest
from dataclasses import replace
from unittest import mock


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.api.system_import import commit_import_context, reset_import_context  # noqa: E402
from app.models.schemas import ImportCommitRequest  # noqa: E402
from app.services.runtime_provider import RuntimeTarget  # noqa: E402


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

    def update_target(self, target: RuntimeTarget, credential_id: str | None = None) -> RuntimeTarget:
        return replace(target, credential_id=credential_id)


class FakeRuntime:
    def __init__(self):
        self.provider = types.SimpleNamespace(name="active-provider")

    async def probe_target(self, target: RuntimeTarget, credentials: dict):
        return {
            "status": "connected",
            "health": {"status": "ok"},
            "system": {"cpu_percent": 10},
            "gpus": [
                {"index": 0, "name": "GPU0", "available": True},
                {"index": 1, "name": "GPU1", "available": True},
            ],
            "capabilities": {},
        }

    async def switch(self, target: RuntimeTarget, credentials: dict):
        return self.provider


class FakeCredentials:
    def save(self, payload: dict) -> str:
        return "cred-1"

    def read(self, credential_id: str) -> dict:
        return {"password": "secret"}


class FakeImportContext:
    def __init__(self):
        self.selected = []

    def save_import(self, **payload):
        self.selected = list(payload["gpu_indexes"])
        return {
            "valid": True,
            "provider_type": payload["provider_type"],
            "agent_label": payload["agent_label"],
            "imported_gpu_indexes": list(payload["gpu_indexes"]),
            "invalid_reason": "",
        }

    def filter_gpus(self, gpus):
        return [gpu for gpu in (gpus or []) if int(gpu.get("index", -1)) in set(self.selected)]

    def filter_processes(self, processes):
        return [proc for proc in (processes or []) if int(proc.get("gpu_index", -1)) in set(self.selected)]

    def clear(self, reason: str):
        self.selected = []
        return {
            "valid": False,
            "provider_type": "http_local",
            "agent_label": "本机 Agent",
            "imported_gpu_indexes": [],
            "invalid_reason": reason,
        }


class FakePrivacy:
    def sanitize_processes(self, processes):
        return list(processes or [])


class SystemImportRuntimeSnapshotTests(unittest.IsolatedAsyncioTestCase):
    async def test_commit_import_context_refreshes_cached_scope_immediately(self):
        fake_app_state = types.SimpleNamespace(
            connection=FakeConnection(),
            runtime=FakeRuntime(),
            credentials=FakeCredentials(),
            import_context=FakeImportContext(),
            privacy=FakePrivacy(),
            latest_runtime_snapshot={
                "collected_at": 1710000000.0,
                "agent_health": {"status": "ok"},
                "runtime": {"status": "connected", "connected": True},
                "import_context": {
                    "valid": False,
                    "imported_gpu_indexes": [],
                    "invalid_reason": "尚未导入任何 GPU",
                },
                "raw": {
                    "system": {"cpu_percent": 10},
                    "gpus": [
                        {"index": 0, "name": "GPU0"},
                        {"index": 1, "name": "GPU1"},
                    ],
                    "processes": [
                        {"pid": 10, "gpu_index": 0},
                        {"pid": 11, "gpu_index": 1},
                    ],
                },
                "scoped": {
                    "system": {"cpu_percent": 10},
                    "gpus": [],
                    "processes": [],
                    "public_processes": [],
                },
            },
        )
        fake_main = types.SimpleNamespace(
            app_state=fake_app_state,
            assign_active_provider=lambda provider: setattr(fake_app_state, "agent", provider),
        )
        request = ImportCommitRequest(
            provider={
                "provider_type": "ssh_linux",
                "label": "训练机 A",
                "host": "10.0.0.8",
                "port": 22,
                "username": "gpuops",
                "auth_type": "password",
                "sudo_enabled": True,
            },
            credentials={"password": "secret", "sudo_password": "rootpw"},
            gpu_indexes=[1],
        )

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            response = await commit_import_context(request)

        self.assertTrue(response["success"])
        self.assertEqual(
            fake_app_state.latest_runtime_snapshot["import_context"]["imported_gpu_indexes"],
            [1],
        )
        self.assertEqual(
            [gpu["index"] for gpu in fake_app_state.latest_runtime_snapshot["scoped"]["gpus"]],
            [1],
        )
        self.assertEqual(
            [proc["pid"] for proc in fake_app_state.latest_runtime_snapshot["scoped"]["processes"]],
            [11],
        )

    async def test_commit_import_context_with_empty_scope_keeps_workspace_valid_and_scoped_empty(self):
        fake_app_state = types.SimpleNamespace(
            connection=FakeConnection(),
            runtime=FakeRuntime(),
            credentials=FakeCredentials(),
            import_context=FakeImportContext(),
            privacy=FakePrivacy(),
            latest_runtime_snapshot={
                "collected_at": 1710000000.0,
                "agent_health": {"status": "ok"},
                "runtime": {"status": "connected", "connected": True},
                "import_context": {
                    "valid": False,
                    "imported_gpu_indexes": [],
                    "invalid_reason": "尚未导入任何 GPU",
                },
                "raw": {
                    "system": {"cpu_percent": 10},
                    "gpus": [
                        {"index": 0, "name": "GPU0"},
                        {"index": 1, "name": "GPU1"},
                    ],
                    "processes": [
                        {"pid": 10, "gpu_index": 0},
                        {"pid": 11, "gpu_index": 1},
                    ],
                },
                "scoped": {
                    "system": {"cpu_percent": 10},
                    "gpus": [],
                    "processes": [],
                    "public_processes": [],
                },
            },
        )
        fake_main = types.SimpleNamespace(
            app_state=fake_app_state,
            assign_active_provider=lambda provider: setattr(fake_app_state, "agent", provider),
        )
        request = ImportCommitRequest(
            provider={
                "provider_type": "ssh_linux",
                "label": "训练机 A",
                "host": "10.0.0.8",
                "port": 22,
                "username": "gpuops",
                "auth_type": "password",
                "sudo_enabled": True,
            },
            credentials={"password": "secret", "sudo_password": "rootpw"},
            gpu_indexes=[],
        )

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            response = await commit_import_context(request)

        self.assertTrue(response["success"])
        self.assertTrue(response["import_context"]["valid"])
        self.assertEqual(response["import_context"]["imported_gpu_indexes"], [])
        self.assertEqual(fake_app_state.latest_runtime_snapshot["scoped"]["gpus"], [])
        self.assertEqual(fake_app_state.latest_runtime_snapshot["scoped"]["processes"], [])

    async def test_reset_import_context_clears_cached_scope_immediately(self):
        fake_app_state = types.SimpleNamespace(
            import_context=FakeImportContext(),
            privacy=FakePrivacy(),
            latest_runtime_snapshot={
                "collected_at": 1710000000.0,
                "agent_health": {"status": "ok"},
                "runtime": {"status": "connected", "connected": True},
                "import_context": {
                    "valid": True,
                    "imported_gpu_indexes": [1],
                    "invalid_reason": "",
                },
                "raw": {
                    "system": {"cpu_percent": 10},
                    "gpus": [
                        {"index": 0, "name": "GPU0"},
                        {"index": 1, "name": "GPU1"},
                    ],
                    "processes": [
                        {"pid": 10, "gpu_index": 0},
                        {"pid": 11, "gpu_index": 1},
                    ],
                },
                "scoped": {
                    "system": {"cpu_percent": 10},
                    "gpus": [{"index": 1, "name": "GPU1"}],
                    "processes": [{"pid": 11, "gpu_index": 1}],
                    "public_processes": [{"pid": 11, "gpu_index": 1}],
                },
            },
        )
        fake_app_state.import_context.selected = [1]
        fake_main = types.SimpleNamespace(app_state=fake_app_state)

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            response = await reset_import_context()

        self.assertTrue(response["success"])
        self.assertEqual(response["import_context"]["imported_gpu_indexes"], [])
        self.assertEqual(fake_app_state.latest_runtime_snapshot["scoped"]["gpus"], [])
        self.assertEqual(fake_app_state.latest_runtime_snapshot["scoped"]["processes"], [])


if __name__ == "__main__":
    unittest.main()
