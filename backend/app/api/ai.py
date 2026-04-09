"""AI对话API - 基于实时数据的LLM智能问答与执行控制台"""

import json

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    AIControlExecuteRequest,
    AIGraphStrategyRequest,
    AIControlPlanRequest,
    ChatRequest,
)
from app.services.ai_control import build_control_context, execute_control_actions, plan_control_actions
from app.services.graph_strategy import build_graph_strategy_context, build_graph_strategy_fallback

router = APIRouter(prefix="/api/ai", tags=["AI"])


@router.post("/chat")
async def chat(req: ChatRequest):
    """AI对话 - 基于实时GPU数据回答能耗相关问题"""
    from app.main import app_state
    if not app_state.llm:
        raise HTTPException(status_code=503, detail="LLM服务未配置")

    # 注入实时GPU数据作为上下文（控制大小防止超token）
    gpus = await app_state.agent.get_all_gpus()
    gpus = app_state.import_context.filter_gpus(gpus)
    system = await app_state.agent.get_system_info()
    processes = await app_state.agent.get_processes()
    processes = app_state.import_context.filter_processes(processes)
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


@router.post("/graph-strategy")
async def graph_strategy(req: AIGraphStrategyRequest):
    """图谱支撑的优化策略与代码模板生成。"""
    from app.main import app_state

    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="请输入优化目标")

    graph_view = await app_state.graph.view_graph(query="", limit=180)
    if not graph_view["ok"]:
        status_code = 503 if not graph_view["neo4j_connected"] or not graph_view["configured"] else 500
        raise HTTPException(status_code=status_code, detail=graph_view["message"])

    control_context = await build_control_context(app_state)
    strategy_context = build_graph_strategy_context(
        message,
        graph_view,
        control_context,
        max_nodes=req.max_nodes,
        max_relationships=req.max_relationships,
    )
    fallback = build_graph_strategy_fallback(message, strategy_context)

    llm_result = None
    if app_state.llm:
        llm_result = await app_state.llm.generate_graph_strategy_plan(
            message,
            strategy_context["context_text"],
            strategy_context["runtime_summary"],
        )

    payload = llm_result or fallback
    return {
        "message": message,
        "summary": payload.get("summary") or fallback["summary"],
        "strategy_steps": payload.get("strategy_steps") or fallback["strategy_steps"],
        "control_prompt": payload.get("control_prompt") or fallback["control_prompt"],
        "code_title": payload.get("code_title") or fallback["code_title"],
        "code_language": payload.get("code_language") or fallback["code_language"],
        "code_snippet": payload.get("code_snippet") or fallback["code_snippet"],
        "risk_notice": payload.get("risk_notice") or fallback["risk_notice"],
        "evidence": payload.get("evidence") or fallback["evidence"],
        "follow_ups": payload.get("follow_ups") or fallback["follow_ups"],
        "used_llm": bool(llm_result),
        "matched_node_count": strategy_context["matched_node_count"],
        "matched_relationship_count": strategy_context["matched_relationship_count"],
        "paper_titles": strategy_context["paper_titles"],
        "evidence_nodes": strategy_context["evidence_nodes"],
        "evidence_relationships": strategy_context["evidence_relationships"],
        "focus": strategy_context["focus"],
        "runtime_summary": strategy_context["runtime_summary"],
    }
