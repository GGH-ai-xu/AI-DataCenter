from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from app.models.schemas import ImportCommitRequest, ImportScanRequest


INVALID_RUNTIME_REASON = "当前导入目标不可达，需要重新导入"
DEFAULT_SSH_PORT = 22
MISSING_SAVED_HOST_DETAIL = "指定主机不存在"

router = APIRouter(prefix="/api/system", tags=["System"])


def _target_source_mode(target) -> str:
    return "local" if target.provider_type == "http_local" else "remote"


def _target_agent_url(target) -> str:
    if target.agent_url:
        return target.agent_url
    return f"ssh://{target.username}@{target.host}:{target.port or DEFAULT_SSH_PORT}"


def _target_public_payload(target) -> dict:
    return {
        "provider_type": target.provider_type,
        "label": target.label,
        "agent_url": target.agent_url,
        "host": target.host,
        "port": target.port,
        "username": target.username,
        "auth_type": target.auth_type,
        "sudo_enabled": target.sudo_enabled,
        "host_fingerprint": target.host_fingerprint,
        "credential_id": target.credential_id,
    }


def _legacy_fields(target) -> dict:
    return {
        "mode": _target_source_mode(target),
        "agent_url": _target_agent_url(target),
        "agent_label": target.label,
    }


def _probe_connected(probe: dict) -> bool:
    return probe.get("status") == "connected" and bool(probe.get("health"))


def _provider_message(connected: bool) -> str:
    return "扫描成功" if connected else "无法连接到目标运行时"


def _probe_error_message(probe: dict) -> str:
    error = str(probe.get("error") or "").strip()
    if error:
        return error
    return _provider_message(False)


def _resolve_route_args(request_or_req, req=None):
    if req is None:
        return None, request_or_req
    return request_or_req, req


@router.get("/import-context")
async def get_import_context():
    from app.main import app_state, resolve_import_context_snapshot, runtime_status_payload

    runtime_status = await runtime_status_payload()
    try:
        health = await app_state.agent.health_check()
        gpus = await app_state.agent.get_all_gpus() if health else []
        return resolve_import_context_snapshot(runtime_status, health, gpus)
    except Exception:
        if runtime_status.get("status") == "invalid":
            return app_state.import_context.mark_invalid(INVALID_RUNTIME_REASON)
        return app_state.import_context.snapshot()


async def _resolve_import_target(
    request: Request | None,
    req: ImportScanRequest | ImportCommitRequest,
):
    from app.main import app_state

    if getattr(req, "saved_host_id", None):
        return await _resolve_saved_host_target(request, int(req.saved_host_id))
    target = app_state.connection.normalize_payload(req.provider_payload())
    owner = _require_authenticated_user(request) if request is not None else None
    return target, req.credential_payload(), owner


async def _resolve_saved_host_target(request: Request | None, host_id: int):
    from app.main import app_state

    if request is None:
        raise HTTPException(status_code=400, detail="saved_host_id 需要请求上下文")
    user = _require_authenticated_user(request)
    try:
        return await app_state.saved_hosts.resolve_for_import(user, host_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        detail = str(exc)
        status = 404 if detail == MISSING_SAVED_HOST_DETAIL else 400
        raise HTTPException(status_code=status, detail=detail) from exc


def _require_authenticated_user(request: Request):
    from app.api import system as system_api

    return system_api.require_authenticated_user(request)


async def scan_import_context(request_or_req, req: ImportScanRequest | None = None):
    from app.main import app_state

    request, req = _resolve_route_args(request_or_req, req)
    try:
        target, credentials, _ = await _resolve_import_target(request, req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    probe = await app_state.runtime.probe_target(target, credentials)
    connected = _probe_connected(probe)
    return {
        "success": connected,
        **_legacy_fields(target),
        "provider": _target_public_payload(target),
        "message": _provider_message(connected) if connected else _probe_error_message(probe),
        "error": probe.get("error", ""),
        "capabilities": probe.get("capabilities", {}),
        "agent_health": probe.get("health"),
        "system": probe.get("system"),
        "gpus": probe.get("gpus", []),
    }


@router.post("/import-context/scan")
async def scan_import_context_route(request: Request, req: ImportScanRequest):
    return await scan_import_context(request, req)


def _missing_gpu_indexes(req: ImportCommitRequest, gpus: list[dict]) -> list[int]:
    available = {int(item.get("index", -1)) for item in gpus}
    return [index for index in req.gpu_indexes if int(index) not in available]


def _raise_for_missing_gpus(missing: list[int]) -> None:
    if not missing:
        return
    missing_text = ", ".join(f"GPU {index}" for index in missing)
    raise HTTPException(status_code=400, detail=f"{missing_text} 当前不存在，无法导入")


def _resolve_active_credentials(target, credentials: dict, credential_id: str | None):
    from app.main import app_state

    if any(credentials.values()):
        return app_state.credentials.save(credentials)
    return target.credential_id or credential_id


async def _activate_import_target(target, credentials: dict, credential_id: str | None):
    from app.main import app_state, assign_active_provider

    saved_target = app_state.connection.update_target(target, credential_id)
    active_secret = app_state.credentials.read(credential_id) if credential_id else {}
    active_provider = await app_state.runtime.switch(saved_target, active_secret)
    assign_active_provider(active_provider)
    return saved_target


def _save_import_context(saved_target, req: ImportCommitRequest, probe: dict) -> dict:
    from app.main import app_state

    return app_state.import_context.save_import(
        source_mode=_target_source_mode(saved_target),
        agent_url=_target_agent_url(saved_target),
        agent_label=saved_target.label,
        gpu_indexes=req.gpu_indexes,
        system_info=probe.get("system"),
        gpus=list(probe.get("gpus") or []),
        provider_type=saved_target.provider_type,
        source_label=saved_target.label,
        target_summary=_target_agent_url(saved_target),
    )


async def commit_import_context(request_or_req, req: ImportCommitRequest | None = None):
    from app.main import app_state

    request, req = _resolve_route_args(request_or_req, req)
    try:
        target, credentials, owner = await _resolve_import_target(request, req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    probe = await app_state.runtime.probe_target(target, credentials)
    if not _probe_connected(probe):
        raise HTTPException(
            status_code=400,
            detail=f"目标运行时不可达，无法完成导入：{_probe_error_message(probe)}",
        )

    gpus = list(probe.get("gpus") or [])
    _raise_for_missing_gpus(_missing_gpu_indexes(req, gpus))
    try:
        credential_id = _resolve_active_credentials(target, credentials, target.credential_id)
        saved_target = await _activate_import_target(target, credentials, credential_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if owner is not None:
        await app_state.saved_hosts.upsert_host(owner, saved_target, credential_id)
    context = _save_import_context(saved_target, req, probe)
    return {
        "success": True,
        "message": "导入完成，控制台已切换到选中的 GPU",
        "import_context": context,
    }


@router.post("/import-context")
async def commit_import_context_route(request: Request, req: ImportCommitRequest):
    return await commit_import_context(request, req)


@router.delete("/import-context")
async def reset_import_context():
    from app.main import app_state

    snapshot = app_state.import_context.clear("用户主动触发重新导入")
    return {"success": True, "import_context": snapshot}
