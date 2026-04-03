"""系统接入配置 API - 连接与 LLM 配置"""

from fastapi import APIRouter, HTTPException

from app.api.auth_access import require_authenticated_user
from app.api.system_diagnostics import self_check
from app.api.system_import import (
    commit_import_context,
    get_import_context,
    reset_import_context,
    scan_import_context,
)
from app.models.schemas import ConnectionConfigRequest, LLMConfigRequest


router = APIRouter(prefix="/api/system", tags=["System"])


@router.get("/connection")
async def get_connection_config():
    from app.main import app_state

    health = await app_state.agent.health_check()
    return app_state.connection.snapshot(health)


@router.post("/connection/test")
async def test_connection_config(req: ConnectionConfigRequest):
    from app.main import app_state

    try:
        mode, target_url = app_state.connection.resolve_target(req.mode, req.agent_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    health = await app_state.connection.probe(target_url)
    return {
        "success": health is not None,
        "mode": mode,
        "agent_url": target_url,
        "agent_label": req.agent_label or ("本机 Agent" if mode == "local" else "远程 Agent"),
        "message": "连接成功" if health is not None else "无法连接到目标 Agent",
        "agent_health": health,
    }


@router.post("/connection")
async def update_connection_config(req: ConnectionConfigRequest):
    from app.main import app_state, assign_active_provider

    payload = {
        "provider_type": "http_remote" if req.mode == "remote" else "http_local",
        "agent_url": req.agent_url,
        "label": req.agent_label,
    }
    try:
        target = app_state.connection.normalize_payload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    saved_target = app_state.connection.update_target(target)
    provider = await app_state.runtime.switch(saved_target, {})
    assign_active_provider(provider)
    health = await provider.health_check()
    return {
        "success": True,
        "message": "接入配置已更新",
        "connection": app_state.connection.snapshot(health),
    }


@router.get("/llm")
async def get_llm_config():
    from app.main import app_state

    return app_state.llm_settings.snapshot(app_state.llm is not None)


@router.post("/llm/test")
async def test_llm(req: LLMConfigRequest):
    from app.main import app_state

    try:
        return await app_state.llm_settings.test(
            req.base_url,
            req.model,
            req.api_key,
            req.keep_existing_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/llm")
async def update_llm(req: LLMConfigRequest):
    from app.main import app_state, bind_llm_service

    try:
        snapshot, llm_service = await app_state.llm_settings.update(
            req.enabled,
            req.base_url,
            req.model,
            req.api_key,
            req.keep_existing_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    bind_llm_service(llm_service)
    return {
        "success": True,
        "message": "AI 助手配置已保存并立即生效" if llm_service else "AI 助手已关闭",
        "llm": snapshot,
    }


__all__ = [
    "commit_import_context",
    "get_import_context",
    "reset_import_context",
    "router",
    "scan_import_context",
    "self_check",
]
