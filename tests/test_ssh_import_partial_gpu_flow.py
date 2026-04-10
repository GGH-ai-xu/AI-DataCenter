import os
import sys
import types
import unittest
from dataclasses import replace
from unittest import mock

from fastapi import HTTPException
from repo_test_bootstrap import prepare_backend_test_env


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
missing_deps = prepare_backend_test_env("cryptography")
if missing_deps:
    raise unittest.SkipTest(f"missing backend test dependencies: {', '.join(missing_deps)}; run install-deps.bat")

from app.api.system import commit_import_context  # noqa: E402
from app.models.schemas import ImportCommitRequest  # noqa: E402
from app.services.runtime_provider import RuntimeTarget  # noqa: E402


class FakeConnection:
    def normalize_payload(self, payload: dict) -> RuntimeTarget:
        return RuntimeTarget(
            provider_type=payload["provider_type"],
            label=payload["label"],
            agent_url=payload.get("agent_url"),
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
        self.probe_result = {
            "status": "connected",
            "health": {"status": "ok"},
            "capabilities": {
                "host_fingerprint": "SHA256:demo",
                "sudo_ready": True,
            },
            "system": {"cpu_percent": 22.5},
            "gpus": [
                {"index": 0, "name": "RTX 4090", "available": True},
                {"index": 1, "name": "RTX 4090", "available": False, "error": "Unknown Error"},
            ],
        }

    async def probe_target(self, target: RuntimeTarget, credentials: dict):
        return dict(self.probe_result)

    async def switch(self, target: RuntimeTarget, credentials: dict):
        return self.provider


class FakeCredentials:
    def __init__(self):
        self.saved = {}

    def save(self, payload: dict) -> str:
        self.saved["cred-1"] = dict(payload)
        return "cred-1"

    def read(self, credential_id: str) -> dict:
        return dict(self.saved[credential_id])


class FakeImportContext:
    def save_import(self, **payload):
        return {
            "valid": True,
            "provider_type": payload["provider_type"],
            "agent_label": payload["agent_label"],
            "imported_gpu_indexes": payload["gpu_indexes"],
        }


class SshImportPartialGpuFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_commit_import_context_rejects_unavailable_gpu_indexes(self):
        fake_app_state = types.SimpleNamespace(
            connection=FakeConnection(),
            runtime=FakeRuntime(),
            credentials=FakeCredentials(),
            import_context=FakeImportContext(),
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
            credentials={
                "password": "secret",
                "sudo_password": "rootpw",
            },
            gpu_indexes=[1],
        )

        with mock.patch("app.main.app_state", fake_app_state):
            with self.assertRaises(HTTPException) as raised:
                await commit_import_context(request)

        self.assertIn("GPU 1 当前不可用", str(raised.exception.detail))


if __name__ == "__main__":
    unittest.main()
