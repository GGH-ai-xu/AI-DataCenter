import os
import sys
import tempfile
import types
import unittest
from dataclasses import replace
from unittest import mock


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.api.system_import import commit_import_context, get_import_context  # noqa: E402
from app.models.schemas import ImportCommitRequest  # noqa: E402
from app.services.runtime_provider import RuntimeTarget  # noqa: E402
from app.services.user_workspace_service import UserWorkspaceService  # noqa: E402
from app.services.workspace_context import workspace_scope  # noqa: E402
from app.services.workspace_proxies import (  # noqa: E402
    WorkspaceAgentProxy,
    WorkspaceImportContextProxy,
    WorkspaceRuntimeProxy,
)


DEFAULT_LOCAL_URL = "http://127.0.0.1:8001"


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
            credential_id=payload.get("credential_id"),
        )


class FakeProvider:
    def __init__(self, target: RuntimeTarget):
        self.target = target

    async def health_check(self):
        return {"status": "ok"}

    async def get_all_gpus(self):
        return [
            {"index": 0, "name": "GPU0", "available": True},
            {"index": 1, "name": "GPU1", "available": True},
        ]

    async def get_processes(self):
        return [
            {"pid": 10, "gpu_index": 0},
            {"pid": 11, "gpu_index": 1},
        ]

    async def get_system_info(self):
        return {"cpu_percent": 12}

    async def close(self):
        return None


class FakeCredentials:
    def save(self, payload: dict) -> str:
        return "cred-1"

    def read(self, credential_id: str) -> dict:
        return {"password": "secret"}


class FakePrivacy:
    def sanitize_processes(self, processes):
        return list(processes or [])


class FakeAppState:
    def __init__(self, workspaces, connection, credentials):
        self.workspaces = workspaces
        self.connection = connection
        self.credentials = credentials
        self.privacy = FakePrivacy()
        self.saved_hosts = types.SimpleNamespace(upsert_host=mock.AsyncMock())
        self.agent = WorkspaceAgentProxy(workspaces)
        self.import_context = WorkspaceImportContextProxy(workspaces)
        self.runtime = WorkspaceRuntimeProxy(workspaces)

    @property
    def latest_runtime_snapshot(self):
        return self.workspaces.current_snapshot()

    @latest_runtime_snapshot.setter
    def latest_runtime_snapshot(self, snapshot):
        self.workspaces.set_current_snapshot(snapshot)


def _build_fake_main(app_state):
    async def runtime_status_payload():
        return await app_state.runtime.status()

    def resolve_import_context_snapshot(runtime_status, agent_health, gpus):
        if runtime_status.get("status") == "connected":
            return app_state.import_context.validate_runtime(agent_health, gpus)
        if runtime_status.get("status") == "invalid":
            return app_state.import_context.mark_invalid("当前导入目标不可达，需要重新导入")
        return app_state.import_context.snapshot()

    return types.SimpleNamespace(
        app_state=app_state,
        assign_active_provider=lambda provider: None,
        resolve_import_context_snapshot=resolve_import_context_snapshot,
        runtime_status_payload=runtime_status_payload,
    )


async def _build_workspace_service(tempdir: str):
    connection = FakeConnection()
    credentials = FakeCredentials()

    def default_target_reader():
        return connection.normalize_payload(
            {
                "provider_type": "http_local",
                "label": "本机 Agent",
                "agent_url": DEFAULT_LOCAL_URL,
            }
        )

    async def provider_factory(target, secret):
        return FakeProvider(target)

    service = UserWorkspaceService(
        runtime_root=tempdir,
        default_local_url=DEFAULT_LOCAL_URL,
        default_target_reader=default_target_reader,
        default_secret_reader=lambda target: credentials.read(target.credential_id) if target.credential_id else {},
        provider_factory=provider_factory,
    )
    await service.ensure_workspace("public")
    return service, connection, credentials


class UserWorkspaceIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspaces, connection, credentials = await _build_workspace_service(self.tempdir.name)
        self.app_state = FakeAppState(self.workspaces, connection, credentials)
        self.fake_main = _build_fake_main(self.app_state)
        self.main_patch = mock.patch.dict(sys.modules, {"app.main": self.fake_main})
        self.main_patch.start()

    async def asyncTearDown(self):
        self.main_patch.stop()
        await self.workspaces.close_all()
        self.tempdir.cleanup()

    async def test_commit_import_context_isolated_between_users(self):
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
            credentials={"password": "secret"},
            gpu_indexes=[1],
        )

        await self.workspaces.ensure_workspace("user:1")
        await self.workspaces.ensure_workspace("user:2")

        with workspace_scope("user:1"):
            response = await commit_import_context(request)

        with workspace_scope("user:2"):
            untouched = await get_import_context()

        self.assertTrue(response["success"])
        self.assertEqual(response["import_context"]["imported_gpu_indexes"], [1])
        self.assertFalse(untouched["valid"])
        self.assertEqual(untouched["imported_gpu_indexes"], [])

    async def test_workspace_snapshots_are_stored_per_user(self):
        await self.workspaces.ensure_workspace("user:1")
        await self.workspaces.ensure_workspace("user:2")

        user_one_snapshot = {
            "collected_at": 1710000001.0,
            "import_context": {"valid": True, "imported_gpu_indexes": [1]},
            "raw": {"system": None, "gpus": [], "processes": []},
            "scoped": {"system": None, "gpus": [{"index": 1}], "processes": [], "public_processes": []},
        }
        user_two_snapshot = {
            "collected_at": 1710000002.0,
            "import_context": {"valid": False, "imported_gpu_indexes": []},
            "raw": {"system": None, "gpus": [], "processes": []},
            "scoped": {"system": None, "gpus": [], "processes": [], "public_processes": []},
        }

        with workspace_scope("user:1"):
            self.workspaces.set_current_snapshot(user_one_snapshot)
        with workspace_scope("user:2"):
            self.workspaces.set_current_snapshot(user_two_snapshot)

        self.assertEqual(
            self.workspaces.require_workspace("user:1").latest_runtime_snapshot["import_context"]["imported_gpu_indexes"],
            [1],
        )
        self.assertEqual(
            self.workspaces.require_workspace("user:2").latest_runtime_snapshot["import_context"]["imported_gpu_indexes"],
            [],
        )

