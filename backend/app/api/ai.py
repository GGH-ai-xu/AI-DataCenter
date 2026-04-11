"""AI对话API - 基于实时数据的LLM智能问答"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.schemas import AiWorkbenchDispatchRequest, ChatRequest
from app.services.llm import LLMService
from app.services.sse import encode_sse_event

MAX_GPU_CONTEXT_CHARS = 4000
MAX_VISIBLE_PROCESSES = 8
GPU_SUMMARY_FIELDS = (
    "index",
    "name",
    "temperature",
    "power_usage",
    "power_limit",
    "gpu_utilization",
    "memory_used",
    "memory_total",
    "fan_speed",
)
SYSTEM_SUMMARY_FIELDS = ("cpu_percent", "cpu_count", "memory_percent", "memory_total")
PROCESS_SUMMARY_FIELDS = (
    "pid",
    "gpu_index",
    "name",
    "command",
    "gpu_memory_used",
    "username",
)

router = APIRouter(prefix="/api/ai", tags=["AI"])


def _pick_fields(items: list[dict], fields: tuple[str, ...]) -> list[dict]:
    return [{key: item[key] for key in fields if key in item} for item in items]


def _truncate_context(text: str) -> str:
    if len(text) <= MAX_GPU_CONTEXT_CHARS:
        return text
    return f"{text[:MAX_GPU_CONTEXT_CHARS]}\n...(数据已截断)"


async def _build_gpu_context(app_state) -> str:
    gpus = await app_state.agent.get_all_gpus()
    system = await app_state.agent.get_system_info()
    processes = await app_state.agent.get_processes()
    gpus = app_state.import_context.filter_gpus(gpus)
    processes = app_state.import_context.filter_processes(processes)
    processes = app_state.privacy.sanitize_processes(processes)

    context_parts: list[str] = []
    gpu_summary = _pick_fields(gpus, GPU_SUMMARY_FIELDS) if gpus else []
    if gpu_summary:
        context_parts.append(
            f"GPU状态:\n{json.dumps(gpu_summary, indent=2, ensure_ascii=False)}"
        )
    if system:
        brief_system = {key: system[key] for key in SYSTEM_SUMMARY_FIELDS if key in system}
        context_parts.append(f"系统资源:\n{json.dumps(brief_system, ensure_ascii=False)}")
    if processes:
        brief_processes = _pick_fields(
            processes[:MAX_VISIBLE_PROCESSES],
            PROCESS_SUMMARY_FIELDS,
        )
        context_parts.append(
            f"GPU进程:\n{json.dumps(brief_processes, indent=2, ensure_ascii=False)}"
        )
    return _truncate_context("\n\n".join(context_parts))


def _require_llm(app_state):
    if not app_state.llm:
        raise HTTPException(status_code=503, detail="LLM服务未配置")
    return app_state.llm


async def _build_session_context(app_state, session_id: str, message: str) -> dict | None:
    session_key = str(session_id or "").strip()
    if not session_key:
        return None
    try:
        return await app_state.goal_runtime.build_session_context_payload(
            session_key,
            message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/chat")
async def chat(req: ChatRequest):
    """AI对话 - 基于实时GPU数据回答能耗相关问题"""
    from app.main import app_state

    llm = _require_llm(app_state)
    gpu_context = await _build_gpu_context(app_state)
    session_context = await _build_session_context(app_state, req.session_id, req.message)
    return await llm.chat(req.message, gpu_context, session_context=session_context)


@router.post("/workbench/dispatch")
async def dispatch_workbench_message(req: AiWorkbenchDispatchRequest):
    from app.main import app_state

    llm = _require_llm(app_state)
    gpu_context = await _build_gpu_context(app_state)
    session_context = await _build_session_context(app_state, req.session_id, req.message)
    try:
        return await llm.dispatch_workbench_message(
            req.message,
            gpu_context,
            session_context=session_context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    from app.main import app_state

    llm = _require_llm(app_state)
    if not llm.supports_chat_stream():
        raise HTTPException(status_code=409, detail="当前模型不支持流式输出")
    gpu_context = await _build_gpu_context(app_state)
    session_context = await _build_session_context(app_state, req.session_id, req.message)

    async def iterator():
        full_text = ""
        yield encode_sse_event("start", {"message": req.message})
        try:
            async for delta in llm.chat_stream(
                req.message,
                gpu_context,
                session_context=session_context,
            ):
                full_text += delta
                yield encode_sse_event("delta", {"text": delta})
                yield encode_sse_event("snapshot", {"text": full_text})
        except Exception as exc:
            yield encode_sse_event("error", {"error": str(exc)})
            return
        yield encode_sse_event(
            "completed",
            {
                "reply": full_text,
                "suggestions": LLMService._extract_suggestions(full_text),
            },
        )

    return StreamingResponse(iterator(), media_type="text/event-stream")
