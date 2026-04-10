from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.models.schemas import (
    ControlCommandApprovalRequest,
    ControlCommandCreateRequest,
)
from app.services.workspace_context import build_workspace_key


router = APIRouter(prefix="/api/control", tags=["Control"])


def _actor_from_request(request: Request) -> tuple[dict, str]:
    user = getattr(request.state, "user", None)
    role = getattr(request.state, "role", None)
    if user is not None:
        return user, build_workspace_key(user, user.get("role"))
    if role:
        actor = {"id": role, "role": role, "username": role}
        return actor, build_workspace_key(None, role)
    raise HTTPException(status_code=401, detail="请先登录平台")


def _raise_control_error(exc: Exception) -> None:
    if isinstance(exc, LookupError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise exc


@router.get("/capabilities")
async def list_control_capabilities(request: Request):
    from app.main import app_state

    user, workspace_key = _actor_from_request(request)
    return {
        "capabilities": await app_state.control_plane.list_capabilities(
            user,
            workspace_key,
        )
    }


@router.get("/catalog")
async def get_control_catalog(request: Request):
    from app.main import app_state

    user, workspace_key = _actor_from_request(request)
    return {
        "domains": await app_state.control_plane.list_catalog(user, workspace_key)
    }


@router.post("/commands")
async def create_control_command(
    request: Request,
    body: ControlCommandCreateRequest,
):
    from app.main import app_state

    user, workspace_key = _actor_from_request(request)
    try:
        return await app_state.control_plane.create_command(body, user, workspace_key)
    except Exception as exc:
        _raise_control_error(exc)


@router.get("/commands")
async def list_control_commands(
    request: Request,
    limit: int = 20,
):
    from app.main import app_state

    user, workspace_key = _actor_from_request(request)
    del user
    return {
        "commands": await app_state.control_plane.list_commands(
            workspace_key,
            limit=limit,
        )
    }


@router.get("/commands/{command_id}")
async def get_control_command(
    command_id: str,
    request: Request,
):
    from app.main import app_state

    user, workspace_key = _actor_from_request(request)
    del user
    try:
        return await app_state.control_plane.get_command(command_id, workspace_key)
    except Exception as exc:
        _raise_control_error(exc)


@router.post("/commands/{command_id}/approve")
async def approve_control_command(
    command_id: str,
    request: Request,
    body: ControlCommandApprovalRequest,
):
    from app.main import app_state

    user, workspace_key = _actor_from_request(request)
    try:
        return await app_state.control_plane.approve_command(
            command_id,
            body,
            user,
            workspace_key,
        )
    except Exception as exc:
        _raise_control_error(exc)
