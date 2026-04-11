from __future__ import annotations

from dataclasses import dataclass
import re


DEFAULT_RECENT_ROUND_LIMIT = 3
DEFAULT_MAX_PROMPT_CHARS = 6000
DEFAULT_SUMMARY_LINE_LIMIT = 6
SUMMARY_COMPRESSION_LIMIT = 1
CHAT_EVENT_TYPES = {
    "UserMessageSubmitted": "user",
    "AssistantMessageGenerated": "assistant",
}
RUNTIME_SUMMARY_EVENT_TYPES = {
    "PlanCreated",
    "AwaitingApproval",
    "SessionCompleted",
    "SessionFailed",
    "LLMCallFailed",
}
ENTITY_PATTERNS = {
    "gpu_indexes": re.compile(r"GPU\s*(\d+)", re.IGNORECASE),
    "job_ids": re.compile(r"\b(job-[A-Za-z0-9_-]+)\b"),
    "pids": re.compile(r"PID\s*(\d+)", re.IGNORECASE),
    "nodes": re.compile(r"\b(node-[A-Za-z0-9_-]+)\b"),
    "queues": re.compile(r"\b(queue-[A-Za-z0-9_-]+)\b"),
}
APPROVAL_REJECTED_EVENT_TYPES = {"ApprovalRejected"}
FAILURE_EVENT_TYPES = {"SessionFailed", "LLMCallFailed"}
SUCCESS_EVENT_TYPES = {"SessionCompleted"}


@dataclass(slots=True)
class SessionContextBudgetError(ValueError):
    message: str

    def __str__(self) -> str:
        return self.message


def _normalize_message(value: str) -> str:
    return str(value or "").strip()


def _collect_round_messages(events: list[dict]) -> list[dict]:
    grouped: dict[int, dict] = {}
    for event in events:
        event_type = str(event.get("event_type") or "")
        role = CHAT_EVENT_TYPES.get(event_type)
        if role is None:
            continue
        content = _normalize_message(event.get("payload", {}).get("content"))
        if not content:
            continue
        round_index = int(event.get("round_index") or 0)
        bucket = grouped.setdefault(round_index, {"round_index": round_index, "messages": []})
        bucket["messages"].append({"role": role, "content": content})
    return [grouped[key] for key in sorted(grouped)]


def _group_events_by_round(events: list[dict]) -> list[dict]:
    grouped: dict[int, list[dict]] = {}
    for event in events:
        round_index = int(event.get("round_index") or 0)
        if round_index <= 0:
            continue
        grouped.setdefault(round_index, []).append(event)
    return [{"round_index": key, "events": grouped[key]} for key in sorted(grouped)]


def _extract_entities(lines: list[str]) -> dict:
    entities = {
        "gpu_indexes": set(),
        "job_ids": set(),
        "pids": set(),
        "nodes": set(),
        "queues": set(),
    }
    joined = "\n".join(lines)
    for key, pattern in ENTITY_PATTERNS.items():
        for token in pattern.findall(joined):
            if key in {"gpu_indexes", "pids"}:
                entities[key].add(int(token))
            else:
                entities[key].add(token)
    return {key: sorted(values) for key, values in entities.items()}


def _event_summary_text(event: dict) -> str:
    payload = event.get("payload", {})
    content = _normalize_message(
        payload.get("summary") or payload.get("content") or payload.get("error")
    )
    return content


def _summarize_historical_rounds(rounds: list[dict], limit: int) -> dict:
    lines = []
    for round_item in rounds:
        fragments = []
        for event in round_item.get("events", []):
            event_type = str(event.get("event_type") or "")
            role = CHAT_EVENT_TYPES.get(event_type)
            if role is not None:
                content = _normalize_message(event.get("payload", {}).get("content"))
                if content:
                    prefix = "用户" if role == "user" else "助手"
                    fragments.append(f"{prefix}：{content}")
                continue
            if event_type in RUNTIME_SUMMARY_EVENT_TYPES:
                content = _event_summary_text(event)
                if content:
                    fragments.append(f"运行：{content}")
        if fragments:
            lines.append("；".join(fragments))
    limited_lines = lines[:limit]
    return {
        "round_count": len(rounds),
        "summary_lines": limited_lines,
        "entities": _extract_entities(limited_lines),
        "constraints": [],
    }


def _last_event_summary(events: list[dict], event_types: set[str], key: str) -> str:
    for event in reversed(events):
        if str(event.get("event_type") or "") not in event_types:
            continue
        payload = event.get("payload", {})
        content = _normalize_message(payload.get(key) or payload.get("summary"))
        if content:
            return content
    return ""


def _detect_approval_status(events: list[dict]) -> str:
    for event in reversed(events):
        event_type = str(event.get("event_type") or "")
        if event_type == "AwaitingApproval":
            return "awaiting_approval"
        if event_type in APPROVAL_REJECTED_EVENT_TYPES:
            return "rejected"
        if event_type in SUCCESS_EVENT_TYPES:
            return "approved"
    return ""


def _summarize_runtime(events: list[dict], session: dict) -> dict:
    return {
        "latest_plan": _last_event_summary(events, {"PlanCreated"}, "summary"),
        "approval_status": _detect_approval_status(events),
        "latest_execution": _last_event_summary(events, SUCCESS_EVENT_TYPES, "summary"),
        "latest_failure": _last_event_summary(events, FAILURE_EVENT_TYPES, "error"),
        "live_phase": _normalize_message(session.get("live_phase") or session.get("status")),
    }


def _format_recent_messages(rounds: list[dict]) -> list[str]:
    lines = ["最近对话原文："]
    if not rounds:
        lines.append("- 无")
        return lines
    for round_item in rounds:
        lines.append(f"第 {round_item['round_index']} 轮")
        for message in round_item.get("messages", []):
            role = "用户" if message["role"] == "user" else "助手"
            lines.append(f"{role}：{message['content']}")
    return lines


def format_session_context_for_prompt(payload: dict) -> str:
    historical_summary = payload.get("historical_summary", {})
    runtime_summary = payload.get("runtime_summary", {})
    lines = ["会话历史摘要："]
    summary_lines = historical_summary.get("summary_lines") or []
    if summary_lines:
        lines.extend(f"- {item}" for item in summary_lines)
    else:
        lines.append("- 无")
    lines.append("")
    lines.extend(_format_recent_messages(payload.get("recent_messages") or []))
    lines.append("")
    lines.append("运行态摘要：")
    lines.append(f"- 最近计划：{runtime_summary.get('latest_plan') or '无'}")
    lines.append(f"- 审批状态：{runtime_summary.get('approval_status') or '无'}")
    lines.append(f"- 最近成功执行：{runtime_summary.get('latest_execution') or '无'}")
    lines.append(f"- 最近失败原因：{runtime_summary.get('latest_failure') or '无'}")
    return "\n".join(lines).strip()


def _build_payload(
    session: dict,
    events: list[dict],
    current_message: str,
    recent_round_limit: int,
    summary_line_limit: int,
) -> dict:
    rounds = _collect_round_messages(events)
    recent_messages = rounds[-recent_round_limit:] if recent_round_limit > 0 else []
    recent_round_indexes = {item["round_index"] for item in recent_messages}
    historical_rounds = [
        item
        for item in _group_events_by_round(events)
        if item["round_index"] not in recent_round_indexes
    ]
    return {
        "session_id": _normalize_message(session.get("session_id")),
        "current_request": {"message": _normalize_message(current_message)},
        "recent_messages": recent_messages,
        "historical_summary": _summarize_historical_rounds(
            historical_rounds,
            summary_line_limit,
        ),
        "runtime_summary": _summarize_runtime(events, session),
    }


def build_session_context_payload(
    session: dict | None,
    events: list[dict],
    current_message: str,
    *,
    recent_round_limit: int = DEFAULT_RECENT_ROUND_LIMIT,
    max_prompt_chars: int = DEFAULT_MAX_PROMPT_CHARS,
) -> dict:
    session_data = dict(session or {})
    payload = _build_payload(
        session_data,
        list(events or []),
        current_message,
        recent_round_limit,
        DEFAULT_SUMMARY_LINE_LIMIT,
    )
    prompt = format_session_context_for_prompt(payload)
    if len(prompt) <= max_prompt_chars:
        return payload

    payload = _build_payload(
        session_data,
        list(events or []),
        current_message,
        recent_round_limit,
        SUMMARY_COMPRESSION_LIMIT,
    )
    prompt = format_session_context_for_prompt(payload)
    if len(prompt) <= max_prompt_chars:
        return payload

    raise SessionContextBudgetError(
        "session context exceeds safe prompt budget after compression"
    )


async def load_session_context_payload(
    store,
    session_id: str,
    current_message: str,
    *,
    recent_round_limit: int = DEFAULT_RECENT_ROUND_LIMIT,
    max_prompt_chars: int = DEFAULT_MAX_PROMPT_CHARS,
) -> dict:
    session = await store.get_agent_session(session_id)
    if session is None:
        raise ValueError(f"session not found: {session_id}")
    events = await store.get_agent_events(session_id)
    return build_session_context_payload(
        session,
        events,
        current_message,
        recent_round_limit=recent_round_limit,
        max_prompt_chars=max_prompt_chars,
    )
