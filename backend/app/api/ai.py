"""AI对话API - 基于实时数据的LLM智能问答与执行控制台"""

import json

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    AIControlExecuteRequest,
    AIControlPlanRequest,
    ChatRequest,
)
from app.services.ai_control import execute_control_actions, plan_control_actions

router = APIRouter(prefix="/api/ai", tags=["AI"])


@router.post("/chat")
async def chat(req: ChatRequest):
    """AI对话 - 基于实时GPU数据回答能耗相关问题"""
    from app.main import app_state
    if not app_state.llm:
        raise HTTPException(status_code=503, detail="LLM服务未配置")

    # 注入实时GPU数据作为上下文（控制大小防止超token）
    gpus = await app_state.agent.get_all_gpus()
    system = await app_state.agent.get_system_info()
    processes = await app_state.agent.get_processes()
    processes = app_state.privacy.sanitize_processes(processes)

    # 精简GPU数据：只保留关键字段
    gpu_summary = [
        {k: g[k] for k in ("index", "name", "temperature", "power_usage",
                            "power_limit", "gpu_utilization", "memory_used",
                            "memory_total", "fan_speed") if k in g}
        for g in gpus
    ] if gpus else []

    context_parts = []
    if gpu_summary:
        context_parts.append(f"GPU状态:\n{json.dumps(gpu_summary, indent=2, ensure_ascii=False)}")
    if system:
        brief_sys = {k: system[k] for k in ("cpu_percent", "cpu_count",
                     "memory_percent", "memory_total") if k in system}
        context_parts.append(f"系统资源:\n{json.dumps(brief_sys, ensure_ascii=False)}")
    if processes:
        brief_procs = [
            {k: p[k] for k in ("pid", "gpu_index", "name", "command",
                                "gpu_memory_used", "username") if k in p}
            for p in processes[:8]
        ]
        context_parts.append(f"GPU进程:\n{json.dumps(brief_procs, indent=2, ensure_ascii=False)}")

    gpu_context = "\n\n".join(context_parts)
    # 硬限制：超过4000字符截断
    if len(gpu_context) > 4000:
        gpu_context = gpu_context[:4000] + "\n...(数据已截断)"

    result = await app_state.llm.chat(req.message, gpu_context)
    return result


@router.post("/control/plan")
async def control_plan(req: AIControlPlanRequest):
    """AI执行控制台 - 先生成动作计划，不直接执行"""
    from app.main import app_state

    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="请输入控制意图")

    return await plan_control_actions(app_state, message)


@router.post("/control/execute")
async def control_execute(req: AIControlExecuteRequest):
    """AI执行控制台 - 执行动作计划"""
    from app.main import app_state

    if not req.actions:
        raise HTTPException(status_code=400, detail="当前没有可执行动作")
    if not req.acknowledge_risk:
        raise HTTPException(status_code=400, detail="执行前请先确认风险")

    payload = [item.model_dump() for item in req.actions]
    return await execute_control_actions(app_state, payload)
