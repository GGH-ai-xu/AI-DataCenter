from __future__ import annotations


FAILURE_EVENT_TYPES = {
    "LLMCallFailed",
    "StepFailed",
    "SessionFailed",
}


def _latest_pending_approval(events: list[dict]) -> dict | None:
    for event in reversed(events):
        if event.get("event_type") != "AwaitingApproval":
            continue
        payload = event.get("payload") or {}
        if payload.get("actions"):
            return payload
    return None


def _latest_error(events: list[dict]) -> str:
    for event in reversed(events):
        if event.get("event_type") not in FAILURE_EVENT_TYPES:
            continue
        payload = event.get("payload") or {}
        error = str(payload.get("error") or "").strip()
        if error:
            return error
    return ""


def build_session_view(session: dict, events: list[dict]) -> dict:
    current_round = 0
    llm_call_count = 0
    for event in events:
        current_round = max(current_round, int(event.get("round_index") or 0))
        if event.get("event_type") == "LLMResponseReceived":
            llm_call_count += 1

    awaiting_approval = session.get("status") == "awaiting_approval"
    pending_approval = _latest_pending_approval(events) if awaiting_approval else None
    return {
        **session,
        "event_count": len(events),
        "current_round": current_round,
        "llm_call_count": llm_call_count,
        "awaiting_approval": awaiting_approval,
        "pending_approval": pending_approval,
        "latest_error": _latest_error(events),
    }
