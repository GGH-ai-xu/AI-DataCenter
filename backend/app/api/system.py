"""系统接入配置 API - 本机 / 远程 Agent 切换"""

import time

from fastapi import APIRouter, HTTPException

from app.models.schemas import ConnectionConfigRequest, LLMConfigRequest
from app.ws.realtime import ws_manager

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


@router.get("/llm")
async def get_llm_config():
    """获取当前 LLM 配置快照"""
    from app.main import app_state

    return app_state.llm_settings.snapshot(app_state.llm is not None)


@router.post("/llm/test")
async def test_llm(req: LLMConfigRequest):
    """测试候选 LLM 配置，不保存"""
    from app.main import app_state

    try:
        result = await app_state.llm_settings.test(
            req.base_url,
            req.model,
            req.api_key,
            req.keep_existing_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return result


@router.post("/llm")
async def update_llm(req: LLMConfigRequest):
    """保存并立即应用 LLM 配置"""
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


@router.get("/self-check")
async def self_check():
    """平台主体链路自检，给首次使用者一个明确的可验证入口"""
    from app.main import app_state

    checked_at = time.time()
    agent_health = await app_state.agent.health_check()
    connection = app_state.connection.snapshot(agent_health)
    gpus = await app_state.agent.get_all_gpus() if agent_health else []
    processes = await app_state.agent.get_processes() if agent_health else []
    system_info = await app_state.agent.get_system_info() if agent_health else None
    budget = app_state.scheduler.get_budget_status(gpus)

    checks = [
        {
            "key": "backend",
            "label": "治理后端",
            "status": "ok",
            "detail": "治理后端在线，REST API 已可用。",
        },
        {
            "key": "connection",
            "label": "接入配置",
            "status": "ok" if connection["connected"] else "warning",
            "detail": (
                f"当前为{connection['mode_label']}，目标 {connection['agent_url']}。"
                if connection["connected"]
                else f"已保存到{connection['mode_label']}，但目标 {connection['agent_url']} 目前不可达。"
            ),
        },
        {
            "key": "agent",
            "label": "采集 Agent",
            "status": "ok" if agent_health else "critical",
            "detail": (
                f"Agent 在线，返回状态 {agent_health.get('status', 'ok')}。"
                if agent_health
                else "Agent 未响应，当前无法采集真实 GPU 与进程数据。"
            ),
        },
        {
            "key": "gpu",
            "label": "GPU 采集",
            "status": "ok" if gpus else "warning",
            "detail": (
                f"已检测到 {len(gpus)} 张真实 GPU。"
                if gpus
                else "Agent 已连通，但当前没有检测到真实 GPU。"
            ),
        },
        {
            "key": "process",
            "label": "进程采集",
            "status": "ok" if agent_health else "warning",
            "detail": (
                f"当前可见 {len(processes)} 个 GPU 进程。"
                if agent_health
                else "由于 Agent 未连通，暂时无法获取 GPU 进程。"
            ),
        },
        {
            "key": "scheduler",
            "label": "治理调度",
            "status": "ok",
            "detail": (
                f"预算治理 {'已启用' if budget['enabled'] else '未启用'}，当前总功率 "
                f"{budget['current_total_power']:.1f}W / {budget['total_power_budget']:.0f}W。"
            ),
        },
        {
            "key": "websocket",
            "label": "实时推送",
            "status": "ok" if ws_manager.connection_count > 0 else "warning",
            "detail": (
                f"当前有 {ws_manager.connection_count} 个前端实时连接。"
                if ws_manager.connection_count > 0
                else "当前还没有活跃的前端实时连接。"
            ),
        },
        {
            "key": "llm",
            "label": "AI 助手",
            "status": "ok" if app_state.llm is not None else "warning",
            "detail": (
                "LLM 已配置，可生成解释与策略建议。"
                if app_state.llm is not None
                else "LLM 未配置，可直接去 AI 页填写 Base URL、Model 与 API Key 后启用。"
            ),
        },
        {
            "key": "system",
            "label": "系统快照",
            "status": "ok" if system_info else "warning",
            "detail": (
                "已获取系统资源快照。"
                if system_info
                else "暂时无法获取系统资源快照。"
            ),
        },
    ]

    if not agent_health:
        summary = {
            "status": "critical",
            "title": "主体链路未打通",
            "message": "治理后端在线，但 Agent 未接通。现在先回到接入中心修复 Agent 连接，再进行后续治理验证。",
        }
    elif not gpus:
        summary = {
            "status": "warning",
            "title": "平台可用，但当前没有真实 GPU 数据",
            "message": "采集链路已通，但还没有拿到真实 GPU。可以先确认接入目标是否真的是带 GPU 的主机。",
        }
    elif ws_manager.connection_count <= 0:
        summary = {
            "status": "warning",
            "title": "平台主体可用，但前端实时连接尚未建立",
            "message": "治理后端、Agent 与 GPU 采集都正常；如果页面指标不刷新，优先检查实时连接。",
        }
    else:
        summary = {
            "status": "ok",
            "title": "平台主体链路可用",
            "message": "现在可以继续做真实治理动作，或先生成一条测试告警，去风险台验证确认链路。",
        }

    return {
        "checked_at": checked_at,
        "summary": summary,
        "checks": checks,
        "connection": connection,
        "budget": budget,
        "agent_connected": bool(agent_health),
        "gpu_count": len(gpus),
        "process_count": len(processes),
        "ws_connections": ws_manager.connection_count,
        "llm_available": app_state.llm is not None,
    }


@router.get("/data-statistics")
async def get_data_statistics():
    """聚合各数据表记录数，展示平台数据采集规模"""
    from app.main import app_state

    return await app_state.store.get_data_statistics()


@router.post("/demo-alert")
async def create_demo_alert():
    """写入一条可安全忽略的测试告警，便于验证风险台链路"""
    from app.main import app_state

    gpus = await app_state.agent.get_all_gpus()
    gpu_index = int(gpus[0].get("index", 0)) if gpus else 0
    alert = {
        "gpu_index": gpu_index,
        "alert_type": "self_check",
        "severity": "warning",
        "message": "平台自检测试告警：用于验证风险台与确认流程，可安全忽略。",
        "value": 1.0,
        "threshold": 0.0,
        "timestamp": time.time(),
    }
    alert_id = await app_state.store.save_alert(alert)
    alert_payload = {
        **alert,
        "id": alert_id,
        "acknowledged": False,
    }

    await ws_manager.broadcast({
        "type": "realtime",
        "alerts": [alert_payload],
    })

    return {
        "success": True,
        "message": "测试告警已写入，接下来可以去风险台验证确认链路。",
        "alert": alert_payload,
    }
