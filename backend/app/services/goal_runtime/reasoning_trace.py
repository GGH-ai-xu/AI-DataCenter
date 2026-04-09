from __future__ import annotations

import json
import time

from app.services.goal_runtime.control_heuristics import build_control_heuristic
from app.services.goal_runtime.executor import execute_capability

TRACE_ROUND_INDEX = 1


def _duration_ms(started_at: float) -> int:
    return max(0, int((time.monotonic() - started_at) * 1000))


def _preview(value, limit: int = 320) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


async def build_reasoning_trace(
    *,
    message: str,
    permission_mode: str,
    registry,
    llm_service,
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
            "round_index": TRACE_ROUND_INDEX,
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
                    "round_index": TRACE_ROUND_INDEX,
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
                    "round_index": TRACE_ROUND_INDEX,
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
    events.append(
        {
            "event_type": "LLMRequestPrepared",
            "payload": {
                "summary": "已准备 LLM 结构化规划请求",
                "prompt_preview": _preview(request_payload),
                "prompt_full": request_payload,
            },
            "round_index": TRACE_ROUND_INDEX,
            "sequence": 2,
            "source": "llm",
            "duration_ms": 0,
        }
    )
    llm_started = time.monotonic()
    try:
        llm_plan = await llm_service.generate_control_plan(
            message,
            _preview(request_payload, limit=1200),
        )
    except Exception as exc:
        llm_plan = None
        llm_error = str(exc)
    else:
        llm_error = "llm returned no structured plan"
    if llm_plan is None:
        heuristic = build_control_heuristic(message)
        events.extend(
            (
                {
                    "event_type": "LLMCallFailed",
                    "payload": {
                        "summary": "LLM 未返回有效结构化计划，切换到规则解析",
                        "error": llm_error,
                    },
                    "round_index": TRACE_ROUND_INDEX,
                    "sequence": 3,
                    "source": "llm",
                    "duration_ms": _duration_ms(llm_started),
                },
                {
                    "event_type": "RuleFallbackUsed",
                    "payload": {
                        "summary": heuristic.get("summary") or "已切换到规则解析",
                        "actions": heuristic.get("actions") or [],
                    },
                    "round_index": TRACE_ROUND_INDEX,
                    "sequence": 4,
                    "source": "planner",
                    "duration_ms": 0,
                },
            )
        )
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
                "round_index": TRACE_ROUND_INDEX,
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
                "round_index": TRACE_ROUND_INDEX,
                "sequence": 4,
                "source": "planner",
                "duration_ms": 0,
            },
        )
    )
    return llm_plan, events
