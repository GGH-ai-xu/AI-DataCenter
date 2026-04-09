from __future__ import annotations

from app.services.goal_runtime.goal_parser import parse_goal_message
from app.services.goal_runtime.planner import build_initial_plan
from app.services.goal_runtime.reasoning_trace import build_reasoning_trace
from app.services.goal_runtime.session_events import build_goal_parsed_event
from app.services.goal_runtime.session_view import build_session_view
from app.services.goal_runtime.supervisor import execute_plan_session

TERMINAL_SESSION_STATUSES = {"completed", "failed", "aborted", "awaiting_approval"}


def _runtime_event_payload(
    session_id: str,
    event_type: str,
    payload: dict,
    metadata: dict,
) -> dict:
    return {
        "session_id": session_id,
        "event_type": event_type,
        "payload": dict(payload),
        "round_index": int(metadata.get("round_index") or 0),
        "sequence": int(metadata.get("sequence") or 0),
        "source": metadata.get("source") or "runtime",
        "duration_ms": int(metadata.get("duration_ms") or 0),
    }


class GoalRuntimeSessionRuntime:
    def __init__(
        self,
        store,
        registry,
        import_context,
        llm_service_reader,
        stream_broker,
    ) -> None:
        self.store = store
        self.registry = registry
        self.import_context = import_context
        self.llm_service_reader = llm_service_reader
        self.stream_broker = stream_broker

    async def append_event(
        self,
        session_id: str,
        event_type: str,
        payload: dict,
        **metadata,
    ) -> None:
        await self.store.append_agent_event(session_id, event_type, payload, **metadata)
        await self.stream_broker.publish(
            session_id,
            "runtime_event",
            _runtime_event_payload(session_id, event_type, payload, metadata),
        )

    async def publish_session_status(
        self,
        session_id: str,
        status: str,
        live_phase: str,
    ) -> None:
        await self.stream_broker.publish(
            session_id,
            "session_status",
            {
                "session_id": session_id,
                "status": status,
                "live_phase": live_phase,
            },
        )

    async def set_session_status(
        self,
        session_id: str,
        status: str,
        summary: str,
        *,
        live_phase: str,
    ) -> None:
        await self.store.update_agent_session_status(
            session_id,
            status,
            summary,
            live_phase=live_phase,
        )
        await self.publish_session_status(session_id, status, live_phase)

    async def publish_planner_snapshot(
        self,
        session_id: str,
        latest_text: str,
        revision: int,
    ) -> None:
        latest_char_count = len(latest_text)
        await self.store.upsert_agent_stream_state(
            session_id,
            "planner",
            latest_text=latest_text,
            latest_char_count=latest_char_count,
            revision=revision,
        )
        await self.stream_broker.publish(
            session_id,
            "planner_snapshot",
            {
                "session_id": session_id,
                "latest_text": latest_text,
                "latest_char_count": latest_char_count,
                "revision": revision,
            },
        )

    async def append_trace_events(
        self,
        session_id: str,
        trace_events: list[dict],
    ) -> None:
        for event in trace_events:
            await self.append_event(
                session_id,
                event["event_type"],
                event["payload"],
                round_index=event["round_index"],
                sequence=event["sequence"],
                source=event["source"],
                duration_ms=event["duration_ms"],
            )

    async def append_plan_created_events(
        self,
        session_id: str,
        goal_spec,
        plan,
        sequence_start: int,
    ) -> None:
        parsed_event = build_goal_parsed_event(
            session_id=session_id,
            goal_type=goal_spec.goal_type,
            permission_mode=goal_spec.permission_mode,
            summary=goal_spec.raw_message,
        )
        await self.append_event(
            session_id,
            parsed_event.event_type,
            dict(parsed_event.payload),
            round_index=1,
            sequence=sequence_start,
            source="planner",
        )
        await self.append_event(
            session_id,
            "PlanCreated",
            {
                "plan_id": plan.plan_id,
                "steps": [
                    {
                        "step_id": step.step_id,
                        "capability_name": step.capability_name,
                        "approval_required": step.approval_required,
                    }
                    for step in plan.steps
                ],
            },
            round_index=1,
            sequence=sequence_start + 1,
            source="planner",
        )

    async def complete_background_run(
        self,
        session_id: str,
        status: str,
        summary: str,
    ) -> None:
        await self.set_session_status(session_id, status, summary, live_phase=status)
        await self.stream_broker.publish(
            session_id,
            "completed",
            {
                "session_id": session_id,
                "status": status,
                "live_phase": status,
            },
        )

    async def run_session(
        self,
        session_id: str,
        message: str,
        permission_mode: str,
    ) -> None:
        try:
            await self.stream_broker.publish(
                session_id,
                "session_started",
                {"session_id": session_id},
            )
            await self.publish_session_status(session_id, "running", "planning")
            planning_result, trace_events = await build_reasoning_trace(
                message=message,
                permission_mode=permission_mode,
                registry=self.registry,
                llm_service=self.llm_service_reader(),
                on_llm_snapshot=lambda text, revision: self.publish_planner_snapshot(
                    session_id,
                    text,
                    revision,
                ),
            )
            goal_spec = await parse_goal_message(
                session_id,
                message,
                permission_mode,
                self.import_context,
                None,
                planning_result=planning_result,
            )
            plan = build_initial_plan(goal_spec, self.registry)
            await self.append_trace_events(session_id, trace_events)
            await self.append_plan_created_events(
                session_id,
                goal_spec,
                plan,
                len(trace_events) + 1,
            )
            await self.set_session_status(
                session_id,
                "running",
                goal_spec.raw_message,
                live_phase="executing",
            )
            result = await execute_plan_session(
                session_id,
                goal_spec,
                plan,
                self.registry,
                self,
            )
            await self.complete_background_run(
                session_id,
                result["status"],
                goal_spec.raw_message,
            )
        except Exception as exc:
            await self.append_event(session_id, "SessionFailed", {"error": str(exc)})
            await self.set_session_status(
                session_id,
                "failed",
                message,
                live_phase="failed",
            )
            await self.stream_broker.publish(
                session_id,
                "error",
                {"session_id": session_id, "error": str(exc)},
            )

    async def get_session(self, session_id: str) -> dict | None:
        session = await self.store.get_agent_session(session_id)
        if session is None:
            return None
        events = await self.store.get_agent_events(session_id)
        planner_stream = await self.store.get_agent_stream_state(session_id, "planner")
        return build_session_view(session, events, planner_stream)

    async def get_events(self, session_id: str) -> list[dict]:
        return await self.store.get_agent_events(session_id)

    async def stream_session(self, session_id: str):
        session = await self.store.get_agent_session(session_id)
        if session is None:
            raise ValueError(f"session not found: {session_id}")
        yield {
            "event": "session_status",
            "data": {
                "session_id": session_id,
                "status": session["status"],
                "live_phase": session.get("live_phase") or session["status"],
            },
        }
        planner_stream = await self.store.get_agent_stream_state(session_id, "planner")
        if planner_stream is not None:
            yield {"event": "planner_snapshot", "data": planner_stream}
        if session["status"] in TERMINAL_SESSION_STATUSES:
            yield {
                "event": "completed",
                "data": {
                    "session_id": session_id,
                    "status": session["status"],
                    "live_phase": session.get("live_phase") or session["status"],
                },
            }
            return
        async for item in self.stream_broker.subscribe(session_id):
            yield item
            if item["event"] in {"completed", "error"}:
                return
