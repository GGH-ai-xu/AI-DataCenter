from __future__ import annotations

import time

from fastapi import APIRouter

from app.services.runtime_snapshot import (
    has_runtime_snapshot,
    snapshot_agent_health,
    snapshot_collected_at,
    snapshot_scoped_gpus,
    snapshot_scoped_processes,
    snapshot_scoped_system,
)
from app.ws.realtime import ws_manager


router = APIRouter(prefix="/api/system", tags=["System"])


def _status_check(key: str, label: str, status: str, detail: str) -> dict:
    return {
        "key": key,
        "label": label,
        "status": status,
        "detail": detail,
    }


def _connection_detail(connection: dict) -> str:
    if connection["connected"]:
        return f"当前为{connection['mode_label']}，目标 {connection['agent_url']}。"
    return f"已保存到{connection['mode_label']}，但目标 {connection['agent_url']} 目前不可达。"


def _build_checks(
    connection: dict,
    agent_health: dict | None,
    gpus: list[dict],
    processes: list[dict],
    llm_available: bool,
    system_info: dict | None,
    budget: dict,
) -> list[dict]:
    return [
        _status_check("backend", "治理后端", "ok", "治理后端在线，REST API 已可用。"),
        _status_check(
            "connection",
            "接入配置",
            "ok" if connection["connected"] else "warning",
            _connection_detail(connection),
        ),
        _status_check(
            "agent",
            "采集 Agent",
            "ok" if agent_health else "critical",
            f"Agent 在线，返回状态 {agent_health.get('status', 'ok')}。"
            if agent_health
            else "Agent 未响应，当前无法采集真实 GPU 与进程数据。",
        ),
        _status_check(
            "gpu",
            "GPU 采集",
            "ok" if gpus else "warning",
            f"已检测到 {len(gpus)} 张真实 GPU。"
            if gpus
            else "Agent 已连通，但当前没有检测到真实 GPU。",
        ),
        _status_check(
            "process",
            "进程采集",
            "ok" if agent_health else "warning",
            f"当前可见 {len(processes)} 个 GPU 进程。"
            if agent_health
            else "由于 Agent 未连通，暂时无法获取 GPU 进程。",
        ),
        _status_check(
            "scheduler",
            "治理调度",
            "ok",
            (
                f"预算治理 {'已启用' if budget['enabled'] else '未启用'}，当前总功率 "
                f"{budget['current_total_power']:.1f}W / {budget['total_power_budget']:.0f}W。"
            ),
        ),
        _status_check(
            "websocket",
            "实时推送",
            "ok" if ws_manager.connection_count > 0 else "warning",
            f"当前有 {ws_manager.connection_count} 个前端实时连接。"
            if ws_manager.connection_count > 0
            else "当前还没有活跃的前端实时连接。",
        ),
        _status_check(
            "llm",
            "AI 助手",
            "ok" if llm_available else "warning",
            "LLM 已配置，可生成解释与策略建议。"
            if llm_available
            else "LLM 未配置，可直接去 AI 页填写 Base URL、Model 与 API Key 后启用。",
        ),
        _status_check(
            "system",
            "系统快照",
            "ok" if system_info else "warning",
            "已获取系统资源快照。"
            if system_info
            else "暂时无法获取系统资源快照。",
        ),
    ]


def _build_summary(
    agent_health: dict | None,
    gpus: list[dict],
) -> dict:
    if not agent_health:
        return {
            "status": "critical",
            "title": "主体链路未打通",
            "message": "治理后端在线，但 Agent 未接通。现在先回到接入中心修复 Agent 连接，再进行后续治理验证。",
        }
    if not gpus:
        return {
            "status": "warning",
            "title": "平台可用，但当前没有真实 GPU 数据",
            "message": "采集链路已通，但还没有拿到真实 GPU。可以先确认接入目标是否真的是带 GPU 的主机。",
        }
    if ws_manager.connection_count <= 0:
        return {
            "status": "warning",
            "title": "平台主体可用，但前端实时连接尚未建立",
            "message": "治理后端、Agent 与 GPU 采集都正常；如果页面指标不刷新，优先检查实时连接。",
        }
    return {
        "status": "ok",
        "title": "平台主体链路可用",
        "message": "现在可以继续做真实治理动作，或进入风险台查看当前真实告警。",
    }


def _cached_self_check_data(app_state, snapshot: dict):
    agent_health = snapshot_agent_health(snapshot)
    connection = app_state.connection.snapshot(agent_health)
    gpus = snapshot_scoped_gpus(snapshot)
    processes = snapshot_scoped_processes(snapshot)
    system_info = snapshot_scoped_system(snapshot)
    budget = app_state.scheduler.get_budget_status(gpus)
    return (
        snapshot_collected_at(snapshot),
        connection,
        agent_health,
        gpus,
        processes,
        system_info,
        budget,
        "cache",
    )


async def _collect_self_check_data():
    from app.main import app_state

    snapshot = getattr(app_state, "latest_runtime_snapshot", {})
    if has_runtime_snapshot(snapshot):
        return _cached_self_check_data(app_state, snapshot)

    agent_health = await app_state.agent.health_check()
    connection = app_state.connection.snapshot(agent_health)
    gpus = await app_state.agent.get_all_gpus() if agent_health else []
    processes = await app_state.agent.get_processes() if agent_health else []
    gpus = app_state.import_context.filter_gpus(gpus)
    processes = app_state.import_context.filter_processes(processes)
    system_info = await app_state.agent.get_system_info() if agent_health else None
    budget = app_state.scheduler.get_budget_status(gpus)
    return time.time(), connection, agent_health, gpus, processes, system_info, budget, "realtime"


@router.get("/self-check")
async def self_check():
    from app.main import app_state

    checked_at, connection, agent_health, gpus, processes, system_info, budget, data_source = await _collect_self_check_data()
    llm_available = app_state.llm is not None
    return {
        "checked_at": checked_at,
        "summary": _build_summary(agent_health, gpus),
        "checks": _build_checks(
            connection,
            agent_health,
            gpus,
            processes,
            llm_available,
            system_info,
            budget,
        ),
        "connection": connection,
        "budget": budget,
        "agent_connected": bool(agent_health),
        "gpu_count": len(gpus),
        "process_count": len(processes),
        "ws_connections": ws_manager.connection_count,
        "llm_available": llm_available,
        "data_source": data_source,
    }
