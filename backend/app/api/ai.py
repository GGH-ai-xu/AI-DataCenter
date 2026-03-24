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

    # 注入实时GPU数据作为上下文
    gpus = await app_state.agent.get_all_gpus()
    system = await app_state.agent.get_system_info()
    processes = await app_state.agent.get_processes()

    context_parts = []
    if gpus:
        context_parts.append(f"GPU状态:\n{json.dumps(gpus, indent=2, ensure_ascii=False)}")
    if system:
        context_parts.append(f"系统资源:\n{json.dumps(system, indent=2, ensure_ascii=False)}")
    if processes:
        context_parts.append(f"GPU进程:\n{json.dumps(processes[:10], indent=2, ensure_ascii=False)}")

    gpu_context = "\n\n".join(context_parts)
    result = await app_state.llm.chat(req.message, gpu_context)
    return result
