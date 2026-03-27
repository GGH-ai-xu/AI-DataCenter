"""系统接入配置 API - 本机 / 远程 Agent 切换"""

from fastapi import APIRouter, HTTPException

from app.models.schemas import ConnectionConfigRequest

router = APIRouter(prefix="/api/system", tags=["System"])


@router.get("/connection")
async def get_connection_config():
    """获取当前接入配置"""
    from app.main import app_state

    health = await app_state.agent.health_check()
    return app_state.connection.snapshot(health)


@router.post("/connection/test")
async def test_connection_config(req: ConnectionConfigRequest):
    """测试候选接入地址，不保存配置"""
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
    """保存并应用接入配置"""
    from app.main import app_state

    try:
        result = await app_state.connection.update(
            app_state.agent,
            req.mode,
            req.agent_url,
            req.agent_label,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "success": True,
        "message": "接入配置已更新",
        "connection": result,
    }
