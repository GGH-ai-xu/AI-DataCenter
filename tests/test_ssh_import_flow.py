import os
import sys
import types
import unittest
from dataclasses import replace
from unittest import mock

from fastapi import HTTPException


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.api.system import commit_import_context, get_import_context, scan_import_context  # noqa: E402
from app.models.schemas import ImportCommitRequest, ImportScanRequest  # noqa: E402
from app.services.runtime_provider import RuntimeTarget  # noqa: E402


class FakeConnection:
    def __init__(self):
        self.updated = []

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
        saved = replace(target, credential_id=credential_id)
        self.updated.append(saved)
        return saved


class FakeRuntime:
    def __init__(self):
        self.switched = []
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
                {"index": 0, "name": "RTX 4090"},
                {"index": 1, "name": "RTX 4090"},
            ],
        }

    async def probe_target(self, target: RuntimeTarget, credentials: dict):
        payload = dict(self.probe_result)
        capabilities = dict(payload.get("capabilities") or {})
        if "host_fingerprint" not in capabilities:
            capabilities["host_fingerprint"] = target.host_fingerprint or "SHA256:demo"
        payload["capabilities"] = capabilities
        return payload

    async def switch(self, target: RuntimeTarget, credentials: dict):
        self.switched.append((target, credentials))
        return self.provider

    async def status(self):
        return {
            "status": "connected",
            "connected": True,
            "provider_type": "ssh_linux",
            "target": {"host": "10.0.0.8"},
            "reconnect_failures": 0,
            "last_error": "",
        }


class FakeCredentials:
    def __init__(self):
        self.saved = {}

    def save(self, payload: dict) -> str:
        self.saved["cred-1"] = dict(payload)
        return "cred-1"

    def read(self, credential_id: str) -> dict:
        return dict(self.saved[credential_id])


class FakeImportContext:
    def __init__(self):
        self.selected = [0]

    def save_import(self, **payload):
        self.selected = list(payload["gpu_indexes"])
        return {
            "valid": True,
            "provider_type": payload["provider_type"],
            "agent_label": payload["agent_label"],
            "imported_gpu_indexes": list(payload["gpu_indexes"]),
        }

    def snapshot(self):
        return {
            "valid": True,
            "provider_type": "ssh_linux",
            "imported_gpu_indexes": list(self.selected),
        }

    def mark_invalid(self, reason: str):
        return {
            "valid": False,
            "invalid_reason": reason,
            "provider_type": "ssh_linux",
            "imported_gpu_indexes": list(self.selected),
        }

    def filter_gpus(self, gpus):
        selected = set(self.selected)
        return [gpu for gpu in (gpus or []) if int(gpu.get("index", -1)) in selected]

    def filter_processes(self, processes):
        selected = set(self.selected)
        return [
            process
            for process in (processes or [])
            if int(process.get("gpu_index", -1)) in selected
        ]


class FakePrivacy:
    def sanitize_processes(self, processes):
        return list(processes or [])


def build_fake_main(app_state):
    async def runtime_status_payload():
        return await app_state.runtime.status()

    def assign_active_provider(provider):
        app_state.agent = provider

    def resolve_import_context_snapshot(runtime_status, agent_health, gpus):
        if runtime_status.get("status") == "connected" and hasattr(app_state.import_context, "validate_runtime"):
            return app_state.import_context.validate_runtime(agent_health, gpus)
        if runtime_status.get("status") == "invalid":
            return app_state.import_context.mark_invalid("当前导入目标不可达，需要重新导入")
        return app_state.import_context.snapshot()

    return types.SimpleNamespace(
        app_state=app_state,
        assign_active_provider=assign_active_provider,
        resolve_import_context_snapshot=resolve_import_context_snapshot,
        runtime_status_payload=runtime_status_payload,
    )


class SshImportFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_scan_import_context_supports_saved_host_id(self):
        saved_hosts = types.SimpleNamespace(
            resolve_for_import=mock.AsyncMock(return_value=(
                RuntimeTarget(
                    provider_type="ssh_linux",
                    label="训练机 A",
                    host="10.0.0.8",
                    port=22,
                    username="gpuops",
                    auth_type="password",
                ),
                {"password": "secret"},
                {"id": 2, "username": "alice", "role": "member", "must_change_password": False},
            )),
        )
        fake_app_state = types.SimpleNamespace(
            connection=FakeConnection(),
            runtime=FakeRuntime(),
            credentials=FakeCredentials(),
            import_context=FakeImportContext(),
            saved_hosts=saved_hosts,
            privacy=FakePrivacy(),
        )
        request = ImportScanRequest(saved_host_id=8)

        with mock.patch.dict(sys.modules, {"app.main": build_fake_main(fake_app_state)}):
            with mock.patch(
                "app.api.system.require_authenticated_user",
                return_value={"id": 2, "username": "alice", "role": "member", "must_change_password": False},
            ):
                response = await scan_import_context(mock.Mock(), request)

        self.assertTrue(response["success"])
        saved_hosts.resolve_for_import.assert_awaited_once()

    async def test_http_import_path_still_returns_connected_snapshot(self):
        fake_app_state = types.SimpleNamespace(
            connection=FakeConnection(),
            runtime=FakeRuntime(),
            credentials=FakeCredentials(),
            import_context=FakeImportContext(),
            privacy=FakePrivacy(),
        )

        request = ImportScanRequest(
            mode="remote",
            agent_url="http://10.0.0.8:8001",
            agent_label="实验室 A",
        )

        with mock.patch.dict(sys.modules, {"app.main": build_fake_main(fake_app_state)}):
            response = await scan_import_context(request)

        self.assertTrue(response["success"])
        self.assertEqual(response["mode"], "remote")
        self.assertEqual(response["provider"]["provider_type"], "http_remote")

    async def test_scan_import_context_returns_ssh_capabilities(self):
        fake_app_state = types.SimpleNamespace(
            connection=FakeConnection(),
            runtime=FakeRuntime(),
            credentials=FakeCredentials(),
            import_context=FakeImportContext(),
            privacy=FakePrivacy(),
        )

        request = ImportScanRequest(
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
        )

        with mock.patch.dict(sys.modules, {"app.main": build_fake_main(fake_app_state)}):
            response = await scan_import_context(request)

        self.assertTrue(response["success"])
        self.assertEqual(response["provider"]["provider_type"], "ssh_linux")
        self.assertEqual(response["provider"]["label"], "训练机 A")
        self.assertIn("host_fingerprint", response["capabilities"])

    async def test_scan_import_context_surfaces_probe_error_message(self):
        runtime = FakeRuntime()
        runtime.probe_result = {
            "status": "offline",
            "health": None,
            "capabilities": {},
            "system": None,
            "gpus": [],
            "error": "SSH 连接超时",
        }
        fake_app_state = types.SimpleNamespace(
            connection=FakeConnection(),
            runtime=runtime,
            credentials=FakeCredentials(),
            import_context=FakeImportContext(),
            privacy=FakePrivacy(),
        )

        request = ImportScanRequest(
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
        )

        with mock.patch.dict(sys.modules, {"app.main": build_fake_main(fake_app_state)}):
            response = await scan_import_context(request)

        self.assertFalse(response["success"])
        self.assertEqual(response["message"], "SSH 连接超时")

    async def test_scan_import_context_surfaces_auth_failure_message(self):
        runtime = FakeRuntime()
        runtime.probe_result = {
            "status": "offline",
            "health": None,
            "capabilities": {},
            "system": None,
            "gpus": [],
            "error": "SSH 认证失败：目标主机拒绝用户 DELL 登录，请检查用户名、密码或私钥。",
        }
        fake_app_state = types.SimpleNamespace(
            connection=FakeConnection(),
            runtime=runtime,
            credentials=FakeCredentials(),
            import_context=FakeImportContext(),
            privacy=FakePrivacy(),
        )

        request = ImportScanRequest(
            provider={
                "provider_type": "ssh_linux",
                "label": "训练机 A",
                "host": "10.151.225.108",
                "port": 22,
                "username": "DELL",
                "auth_type": "password",
                "sudo_enabled": True,
            },
            credentials={
                "password": "bad",
                "sudo_password": "bad",
            },
        )

        with mock.patch.dict(sys.modules, {"app.main": build_fake_main(fake_app_state)}):
            response = await scan_import_context(request)

        self.assertFalse(response["success"])
        self.assertIn("目标主机拒绝用户 DELL 登录", response["message"])

    async def test_commit_import_context_rejects_missing_selected_gpu(self):
        fake_app_state = types.SimpleNamespace(
            connection=FakeConnection(),
            runtime=FakeRuntime(),
            credentials=FakeCredentials(),
            import_context=FakeImportContext(),
            privacy=FakePrivacy(),
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
            gpu_indexes=[9],
        )

        with mock.patch.dict(sys.modules, {"app.main": build_fake_main(fake_app_state)}):
            with self.assertRaises(HTTPException):
                await commit_import_context(request)

    async def test_commit_import_context_uses_probe_error_detail(self):
        runtime = FakeRuntime()
        runtime.probe_result = {
            "status": "offline",
            "health": None,
            "capabilities": {},
            "system": None,
            "gpus": [],
            "error": "SSH 认证失败",
        }
        fake_app_state = types.SimpleNamespace(
            connection=FakeConnection(),
            runtime=runtime,
            credentials=FakeCredentials(),
            import_context=FakeImportContext(),
            privacy=FakePrivacy(),
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
            gpu_indexes=[0],
        )

        with mock.patch.dict(sys.modules, {"app.main": build_fake_main(fake_app_state)}):
            with self.assertRaises(HTTPException) as raised:
                await commit_import_context(request)

        self.assertIn("SSH 认证失败", str(raised.exception.detail))

    async def test_commit_import_context_updates_active_agent_alias(self):
        runtime = FakeRuntime()
        fake_app_state = types.SimpleNamespace(
            connection=FakeConnection(),
            runtime=runtime,
            credentials=FakeCredentials(),
            import_context=FakeImportContext(),
            agent=None,
            privacy=FakePrivacy(),
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
            gpu_indexes=[0],
        )

        with mock.patch.dict(sys.modules, {"app.main": build_fake_main(fake_app_state)}):
            await commit_import_context(request)

        self.assertIs(fake_app_state.agent, runtime.provider)

    async def test_get_import_context_keeps_snapshot_during_reconnect(self):
        runtime = FakeRuntime()
        base_status = runtime.status

        async def reconnecting_status():
            payload = await base_status()
            payload["status"] = "reconnecting"
            payload["connected"] = False
            return payload

        runtime.status = reconnecting_status
        fake_app_state = types.SimpleNamespace(
            runtime=runtime,
            import_context=FakeImportContext(),
            agent=types.SimpleNamespace(
                health_check=mock.AsyncMock(side_effect=RuntimeError("dial tcp timeout")),
                get_all_gpus=mock.AsyncMock(return_value=[]),
            ),
        )

        with mock.patch.dict(sys.modules, {"app.main": build_fake_main(fake_app_state)}):
            response = await get_import_context()

        self.assertTrue(response["valid"])
        self.assertEqual(response["provider_type"], "ssh_linux")


if __name__ == "__main__":
    unittest.main()
