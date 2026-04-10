from __future__ import annotations

import uuid

from app.services.control_plane.catalog import (
    group_capabilities_by_domain,
    list_manual_capabilities,
)
from app.services.control_plane.models import ControlCommandRecord
from app.services.control_plane.policy import ensure_confirmation, ensure_manual_access
from app.services.goal_runtime.executor import execute_capability


SUCCESS_STATE = "succeeded"
FAILED_STATE = "failed"
PENDING_APPROVAL_STATE = "pending"
AWAITING_APPROVAL_EXECUTION = "awaiting_approval"


def _operator_id(user: dict) -> str:
    return str(user.get("username") or user.get("id") or "unknown")


def _initial_states(permission_mode: str) -> tuple[str, str]:
    if permission_mode == "approval_required":
        return PENDING_APPROVAL_STATE, AWAITING_APPROVAL_EXECUTION
    if permission_mode == "confirm_required":
        return "approved", "queued"
    return "not_required", "queued"


def _result_summary(result: dict) -> str:
    if result["success"]:
        output = result.get("output")
        if isinstance(output, dict) and output.get("pid"):
            return f"执行成功 · PID {output['pid']}"
        return "执行成功"
    return result.get("error") or "执行失败"


def _serialize(record: dict | None) -> dict | None:
    return record


class ControlPlaneService:
    def __init__(self, store, registry):
        self.store = store
        self.registry = registry

    async def list_capabilities(self, user: dict, workspace_key: str) -> list[dict]:
        del workspace_key
        items = []
        for item in list_manual_capabilities(self.registry):
            registered = self.registry.get(item["name"])
            try:
                ensure_manual_access(registered.definition, user)
            except (LookupError, PermissionError):
                continue
            items.append(item)
        return items

    async def list_catalog(self, user: dict, workspace_key: str) -> list[dict]:
        return group_capabilities_by_domain(
            await self.list_capabilities(user, workspace_key)
        )

    async def create_command(self, request, user: dict, workspace_key: str) -> dict:
        registered = self.registry.get(request.capability_name)
        policy = ensure_manual_access(registered.definition, user)
        ensure_confirmation(policy, request)
        record = ControlCommandRecord(
            command_id=uuid.uuid4().hex,
            capability_name=registered.definition.name,
            domain=registered.definition.domain,
            operator_id=_operator_id(user),
            operator_type="manual",
            workspace_key=workspace_key,
            source_page=request.source_page,
            arguments=dict(request.arguments),
            risk_level=policy.risk_level,
            permission_mode=policy.permission_mode,
            approval_state=_initial_states(policy.permission_mode)[0],
            execution_state=_initial_states(policy.permission_mode)[1],
            result_summary="",
            error_message="",
            related_session_id=request.related_session_id,
        )
        await self.store.create_control_command(record)
        if policy.permission_mode == "approval_required":
            return await self.get_command(record.command_id, workspace_key)
        return await self._execute_command(record.command_id)

    async def list_commands(
        self,
        workspace_key: str,
        *,
        limit: int = 20,
    ) -> list[dict]:
        return await self.store.list_control_commands(
            workspace_key=workspace_key,
            limit=limit,
        )

    async def get_command(
        self,
        command_id: str,
        workspace_key: str,
    ) -> dict:
        record = await self._load_command(command_id, workspace_key)
        return _serialize(record)

    async def approve_command(
        self,
        command_id: str,
        request,
        user: dict,
        workspace_key: str,
    ) -> dict:
        del user
        record = await self._load_command(command_id, workspace_key)
        if record["approval_state"] != PENDING_APPROVAL_STATE:
            raise ValueError("该命令当前不处于待审批状态")
        if not request.approved:
            await self.store.update_control_command(
                command_id,
                {
                    "approval_state": "rejected",
                    "execution_state": "rejected",
                    "result_summary": request.comment or "审批已拒绝",
                },
            )
            return await self.get_command(command_id, workspace_key)
        await self.store.update_control_command(
            command_id,
            {
                "approval_state": "approved",
                "result_summary": request.comment or "",
            },
        )
        return await self._execute_command(command_id)

    async def _load_command(self, command_id: str, workspace_key: str) -> dict:
        record = await self.store.get_control_command(command_id)
        if record is None:
            raise LookupError("control command not found")
        if record["workspace_key"] != workspace_key:
            raise PermissionError("当前工作区无权访问该命令")
        return record

    async def _execute_command(self, command_id: str) -> dict:
        record = await self.store.get_control_command(command_id)
        if record is None:
            raise LookupError("control command not found")
        result = await execute_capability(
            self.registry,
            record["capability_name"],
            {"workspace_key": record["workspace_key"]},
            record["arguments"],
        )
        await self.store.update_control_command(
            command_id,
            {
                "execution_state": SUCCESS_STATE if result["success"] else FAILED_STATE,
                "result_summary": _result_summary(result),
                "error_message": result["error"],
            },
        )
        return await self.store.get_control_command(command_id)
