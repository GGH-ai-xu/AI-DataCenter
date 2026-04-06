import os
import sys
import tempfile
import types
import unittest
from unittest import mock

from fastapi import HTTPException


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.api.system import commit_import_context, scan_import_context  # noqa: E402
from app.models.schemas import ImportCommitRequest, ImportScanRequest  # noqa: E402
from app.services.credential_store import CredentialStore  # noqa: E402
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
        return target


class FakeRuntime:
    async def probe_target(self, target: RuntimeTarget, credentials: dict):
        return {
            "status": "connected",
            "health": {"status": "ok"},
            "system": {"cpu_percent": 10},
            "gpus": [{"index": 0, "name": "RTX 4090"}],
            "capabilities": {},
        }


class FakeImportContext:
    def save_import(self, **payload):
        return {
            "valid": True,
            "provider_type": payload["provider_type"],
            "imported_gpu_indexes": payload["gpu_indexes"],
        }


class SystemImportErrorTests(unittest.IsolatedAsyncioTestCase):
    async def test_commit_import_context_returns_http_400_when_master_key_missing(self):
        tempdir = tempfile.TemporaryDirectory()
        self.addAsyncCleanup(lambda: _cleanup_tempdir(tempdir))
        fake_app_state = types.SimpleNamespace(
            connection=FakeConnection(),
            runtime=FakeRuntime(),
            credentials=CredentialStore(os.path.join(tempdir.name, "credentials.json"), None),
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
            credentials={"password": "secret", "sudo_password": "rootpw"},
            gpu_indexes=[0],
        )

        with mock.patch("app.main.app_state", fake_app_state):
            with self.assertRaises(HTTPException) as raised:
                await commit_import_context(request)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("GPU_GOV_MASTER_KEY", str(raised.exception.detail))

    async def test_scan_saved_host_returns_http_400_when_credentials_cannot_be_read(self):
        saved_hosts = types.SimpleNamespace(
            resolve_for_import=mock.AsyncMock(
                side_effect=ValueError("平台未配置主密钥 GPU_GOV_MASTER_KEY，无法保存或读取 SSH 凭据")
            ),
        )
        fake_app_state = types.SimpleNamespace(saved_hosts=saved_hosts)
        request = ImportScanRequest(saved_host_id=8)

        with mock.patch("app.main.app_state", fake_app_state):
            with mock.patch(
                "app.api.system.require_authenticated_user",
                return_value={"id": 1, "username": "admin", "role": "admin", "must_change_password": False},
            ):
                with self.assertRaises(HTTPException) as raised:
                    await scan_import_context(mock.Mock(), request)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("GPU_GOV_MASTER_KEY", str(raised.exception.detail))


def _cleanup_tempdir(tempdir: tempfile.TemporaryDirectory) -> None:
    tempdir.cleanup()


if __name__ == "__main__":
    unittest.main()
