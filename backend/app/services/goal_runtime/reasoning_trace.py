from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

from app.services.goal_runtime.control_heuristics import build_control_heuristic
from app.services.goal_runtime.executor import execute_capability
from app.services.llm import LLMService

DEFAULT_TRACE_ROUND_INDEX = 1
SNAPSHOT_FLUSH_INTERVAL_CHARS = 48
PlanSnapshotCallback = Callable[[str, int], Awaitable[None]]
PlanDeltaCallback = Callable[[str], Awaitable[None]]


def _duration_ms(started_at: float) -> int:
    return max(0, int((time.monotonic() - started_at) * 1000))


def _preview(value: Any, limit: int = 320) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _supports_control_plan_stream(llm_service: Any) -> bool:
    checker = getattr(llm_service, "supports_control_plan_stream", None)
    return bool(callable(checker) and checker())


async def _maybe_emit_snapshot(
    text: str,
    last_char_count: int,
    revision: int,
    on_llm_snapshot: PlanSnapshotCallback | None,
    *,
    force: bool = False,
) -> tuple[int, int]:
    if on_llm_snapshot is None:
        return last_char_count, revision
    current_count = len(text)
    if current_count == last_char_count:
        return last_char_count, revision
    should_flush = force or current_count - last_char_count >= SNAPSHOT_FLUSH_INTERVAL_CHARS
    if not should_flush:
        return last_char_count, revision
    next_revision = revision + 1
    await on_llm_snapshot(text, next_revision)
    return current_count, next_revision


async def _collect_streamed_plan(
    llm_service: Any,
    message: str,
    control_context: str,
    on_llm_delta: PlanDeltaCallback | None,
    on_llm_snapshot: PlanSnapshotCallback | None,
) -> dict | None:
    revision = 0
    streamed_text = ""
    last_char_count = 0
    async for delta in llm_service.generate_control_plan_stream(message, control_context):
        streamed_text += delta
        if on_llm_delta is not None:
            await on_llm_delta(delta)
        last_char_count, revision = await _maybe_emit_snapshot(
            streamed_text,
            last_char_count,
            revision,
            on_llm_snapshot,
        )
    await _maybe_emit_snapshot(
        streamed_text,
        last_char_count,
        revision,
        on_llm_snapshot,
        force=True,
    )
    if not streamed_text.strip():
        return None
    return LLMService.parse_structured_json(
        streamed_text,
        label="LLM 返回的流式控制计划",
    )


async def _load_llm_plan(
    llm_service: Any,
    message: str,
    control_context: str,
    on_llm_delta: PlanDeltaCallback | None,
    on_llm_snapshot: PlanSnapshotCallback | None,
) -> dict | None:
    if _supports_control_plan_stream(llm_service):
        return await _collect_streamed_plan(
            llm_service,
            message,
            control_context,
            on_llm_delta,
            on_llm_snapshot,
        )
    return await llm_service.generate_control_plan(message, control_context)


def _build_fallback_events(
    summary: str,
    actions: list[dict],
    error: str,
    *,
    round_index: int,
) -> list[dict]:
    return [
        {
            "event_type": "LLMCallFailed",
            "payload": {
                "summary": "LLM 未返回有效结构化计划，切换到规则解析",
                "error": error,
            },
            "round_index": round_index,
            "sequence": 3,
            "source": "llm",
            "duration_ms": 0,
        },
        {
            "event_type": "RuleFallbackUsed",
            "payload": {
                "summary": summary or "已切换到规则解析",
                "actions": actions,
            },
            "round_index": round_index,
            "sequence": 4,
            "source": "planner",
            "duration_ms": 0,
        },
    ]


async def build_reasoning_trace(
    *,
    message: str,
    permission_mode: str,
    registry,
    llm_service,
    round_index: int = DEFAULT_TRACE_ROUND_INDEX,
    session_context: dict | None = None,
    session_context_text: str = "",
    on_llm_delta: PlanDeltaCallback | None = None,
    on_llm_snapshot: PlanSnapshotCallback | None = None,
) -> tuple[dict, list[dict]]:
    snapshot_started = time.monotonic()
    snapshot_result = await execute_capability(registry, "runtime.snapshot.read", {}, {})
    snapshot = snapshot_result.get("output") if snapshot_result.get("success") else {}
    events = [
        {
            "event_type": "ContextSnapshotCaptured",
            "payload": {
                "summary": "已采集当前运行时快照",
                "snapshot_preview": snapshot,
            },
            "round_index": round_index,
            "sequence": 1,
            "source": "planner",
            "duration_ms": _duration_ms(snapshot_started),
        }
    ]
    if llm_service is None:
        heuristic = build_control_heuristic(message)
        events.extend(
            (
                {
                    "event_type": "LLMUnavailable",
                    "payload": {"summary": "当前未配置 LLM，切换到规则解析"},
                    "round_index": round_index,
                    "sequence": 2,
                    "source": "llm",
                    "duration_ms": 0,
                },
                {
                    "event_type": "RuleFallbackUsed",
                    "payload": {
                            "summary": heuristic.get("summary") or "已切换到规则解析",
                            "actions": heuristic.get("actions") or [],
                        },
                    "round_index": round_index,
                    "sequence": 3,
                    "source": "planner",
                    "duration_ms": 0,
                },
            )
        )
        return heuristic, events

    request_payload = {
        "message": message,
        "permission_mode": permission_mode,
        "snapshot": snapshot,
    }
    if session_context is not None:
        request_payload["session_context"] = session_context
    if session_context_text:
        request_payload["session_context_text"] = session_context_text
    events.append(
        {
            "event_type": "LLMRequestPrepared",
            "payload": {
                "summary": "已准备 LLM 结构化规划请求",
                "prompt_preview": _preview(request_payload),
                "prompt_full": request_payload,
            },
            "round_index": round_index,
            "sequence": 2,
            "source": "llm",
            "duration_ms": 0,
        }
    )
    llm_started = time.monotonic()
    try:
        llm_plan = await _load_llm_plan(
            llm_service,
            message,
            _preview(request_payload, limit=1200),
            on_llm_delta,
            on_llm_snapshot,
        )
    except Exception as exc:
        heuristic = build_control_heuristic(message)
        events.extend(
            _build_fallback_events(
                heuristic.get("summary") or "",
                heuristic.get("actions") or [],
                str(exc),
                round_index=round_index,
            )
        )
        events[-2]["duration_ms"] = _duration_ms(llm_started)
        return heuristic, events
    if llm_plan is None:
        heuristic = build_control_heuristic(message)
        events.extend(
            _build_fallback_events(
                heuristic.get("summary") or "",
                heuristic.get("actions") or [],
                "llm returned no structured plan",
                round_index=round_index,
            )
        )
        events[-2]["duration_ms"] = _duration_ms(llm_started)
        return heuristic, events

    events.extend(
        (
            {
                "event_type": "LLMResponseReceived",
                "payload": {
                    "summary": llm_plan.get("summary") or "LLM 已返回结构化计划",
                    "response_preview": _preview(llm_plan),
                    "response_full": llm_plan,
                },
                "round_index": round_index,
                "sequence": 3,
                "source": "llm",
                "duration_ms": _duration_ms(llm_started),
            },
            {
                "event_type": "LLMPlanExtracted",
                "payload": {
                    "summary": llm_plan.get("summary") or "已提取结构化计划",
                    "structured_plan": llm_plan,
                },
                "round_index": round_index,
                "sequence": 4,
                "source": "planner",
                "duration_ms": 0,
            },
        )
    )
    return llm_plan, events
