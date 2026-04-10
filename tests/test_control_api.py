import os
import sys
import tempfile
import types
import unittest
from unittest import mock


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.models.schemas import (  # noqa: E402
    ControlCommandApprovalRequest,
    ControlCommandCreateRequest,
)
from app.services.data_store import DataStore  # noqa: E402
from app.services.goal_runtime.capability import (  # noqa: E402
    CapabilityDefinition,
    CapabilityManualControl,
)
from app.services.goal_runtime.capability_registry import CapabilityRegistry  # noqa: E402
from app.services.control_plane.service import ControlPlaneService  # noqa: E402
from app.api.control import (  # noqa: E402
    approve_control_command,
    create_control_command,
    list_control_capabilities,
)


def _manual(
    *,
    enabled: bool = True,
    label: str,
    description: str,
    required_role: str = "member",
    risk_level: str = "observe",
    approval_policy: str = "direct",
):
    return CapabilityManualControl(
        enabled=enabled,
        label=label,
        description=description,
        required_role=required_role,
        risk_level=risk_level,
        approval_policy=approval_policy,
    )


def _user(user_id: int, role: str) -> dict:
    return {"id": user_id, "role": role, "username": f"user-{user_id}"}


class ControlPlaneServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.store = DataStore(os.path.join(self.tmpdir.name, "control.db"))
        await self.store.init()
        self.registry = CapabilityRegistry()
        self._register_capabilities()
        self.service = ControlPlaneService(self.store, self.registry)

    async def asyncTearDown(self):
        await self.store.close()
        self.tmpdir.cleanup()

    def _register_capabilities(self):
        async def read_snapshot(_context, _arguments):
            return {"gpus": [{"index": 0}]}

        async def pause_task(_context, arguments):
            return {"success": True, "pid": int(arguments["pid"])}

        async def terminate_task(_context, arguments):
            return {"success": True, "pid": int(arguments["pid"])}

        self.registry.register(
            CapabilityDefinition(
                "runtime.snapshot.read",
                "runtime",
                "observe",
                False,
                ("http_local",),
                manual_control=_manual(
                    label="读取快照",
                    description="读取当前运行时快照",
                    required_role="observer",
                    risk_level="observe",
                    approval_policy="direct",
                ),
            ),
            handler=read_snapshot,
        )
        self.registry.register(
            CapabilityDefinition(
                "tasks.pause",
                "tasks",
                "runtime_action",
                True,
                ("http_local",),
                manual_control=_manual(
                    label="暂停任务",
                    description="暂停指定任务",
                    required_role="member",
                    risk_level="control",
                    approval_policy="confirm_required",
                ),
            ),
            handler=pause_task,
        )
        self.registry.register(
            CapabilityDefinition(
                "tasks.terminate",
                "tasks",
                "runtime_action",
                True,
                ("http_local",),
                manual_control=_manual(
                    label="终止任务",
                    description="终止指定任务",
                    required_role="admin",
                    risk_level="dangerous",
                    approval_policy="approval_required",
                ),
            ),
            handler=terminate_task,
        )
        self.registry.register(
            CapabilityDefinition(
                "job.cancel",
                "jobs",
                "runtime_action",
                False,
                ("http_local",),
            ),
            handler=terminate_task,
        )

    async def test_list_capabilities_filters_by_manual_flag_and_role(self):
        items = await self.service.list_capabilities(_user(2, "member"), "user:2")
        names = [item["name"] for item in items]

        self.assertEqual(names, ["runtime.snapshot.read", "tasks.pause"])

    async def test_create_command_requires_ack_for_confirm_required_capability(self):
        with self.assertRaisesRegex(ValueError, "确认风险"):
            await self.service.create_command(
                ControlCommandCreateRequest(
                    capability_name="tasks.pause",
                    arguments={"pid": 42},
                    source_page="governance-actions",
                ),
                _user(2, "member"),
                "user:2",
            )

    async def test_create_command_executes_direct_capability_and_persists_result(self):
        payload = await self.service.create_command(
            ControlCommandCreateRequest(
                capability_name="runtime.snapshot.read",
                arguments={},
                source_page="governance-actions",
            ),
            _user(2, "member"),
            "user:2",
        )
        stored = await self.store.get_control_command(payload["command_id"])

        self.assertEqual(payload["execution_state"], "succeeded")
        self.assertEqual(payload["approval_state"], "not_required")
        self.assertEqual(stored["workspace_key"], "user:2")

    async def test_approve_command_executes_pending_record(self):
        created = await self.service.create_command(
            ControlCommandCreateRequest(
                capability_name="tasks.terminate",
                arguments={"pid": 99},
                source_page="governance-actions",
            ),
            _user(1, "admin"),
            "user:1",
        )

        self.assertEqual(created["approval_state"], "pending")
        self.assertEqual(created["execution_state"], "awaiting_approval")

        approved = await self.service.approve_command(
            created["command_id"],
            ControlCommandApprovalRequest(approved=True, comment="批准执行"),
            _user(1, "admin"),
            "user:1",
        )

        self.assertEqual(approved["approval_state"], "approved")
        self.assertEqual(approved["execution_state"], "succeeded")


class ControlApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_capability_catalog_hides_non_manual_capabilities(self):
        app_state = types.SimpleNamespace(control_plane=mock.AsyncMock())
        app_state.control_plane.list_capabilities.return_value = [{"name": "tasks.pause"}]
        fake_main = types.SimpleNamespace(app_state=app_state)
        request = types.SimpleNamespace(
            state=types.SimpleNamespace(user=_user(2, "member"))
        )

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            payload = await list_control_capabilities(request)

        self.assertEqual(payload["capabilities"][0]["name"], "tasks.pause")

    async def test_member_must_acknowledge_confirm_required_capability(self):
        app_state = types.SimpleNamespace(control_plane=mock.AsyncMock())
        app_state.control_plane.create_command.side_effect = ValueError(
            "真实执行前请先确认风险"
        )
        fake_main = types.SimpleNamespace(app_state=app_state)
        request = types.SimpleNamespace(
            state=types.SimpleNamespace(user=_user(2, "member"))
        )

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            with self.assertRaises(Exception):
                await create_control_command(
                    request,
                    ControlCommandCreateRequest(
                        capability_name="tasks.pause",
                        arguments={"pid": 42},
                        acknowledge_risk=False,
                    ),
                )

    async def test_approve_command_returns_updated_record(self):
        app_state = types.SimpleNamespace(control_plane=mock.AsyncMock())
        app_state.control_plane.approve_command.return_value = {
            "command_id": "cmd-1",
            "execution_state": "succeeded",
        }
        fake_main = types.SimpleNamespace(app_state=app_state)
        request = types.SimpleNamespace(
            state=types.SimpleNamespace(user=_user(1, "admin"))
        )

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            payload = await approve_control_command(
                "cmd-1",
                request,
                ControlCommandApprovalRequest(approved=True),
            )

        self.assertEqual(payload["execution_state"], "succeeded")


if __name__ == "__main__":
    unittest.main()
