"""AI对话API - 基于实时数据的LLM智能问答"""

import json

from fastapi import APIRouter, HTTPException

from app.models.schemas import ChatRequest

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
