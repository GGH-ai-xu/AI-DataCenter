from __future__ import annotations

import asyncio
from uuid import uuid4

from app.services.goal_runtime.approval_runtime import GoalRuntimeApprovalRuntime
from app.services.goal_runtime.goal_parser import parse_goal_message
from app.services.goal_runtime.planner import build_initial_plan
from app.services.goal_runtime.session_context import load_session_context_payload
from app.services.goal_runtime.session_runtime import (
    GoalRuntimeSessionRuntime,
    TERMINAL_SESSION_STATUSES,
)
from app.services.goal_runtime.session_stream import GoalRuntimeSessionStreamBroker


ACTIVE_SESSION_STATUSES = {"running", "awaiting_approval"}


class GoalRuntimeService:
    def __init__(
        self,
        store,
        registry,
        import_context,
        runtime_status_reader,
        llm_service_reader=None,
        task_spawner=None,
        stream_broker=None,
    ) -> None:
        self.store = store
        self.registry = registry
        self.import_context = import_context
        self.runtime_status_reader = runtime_status_reader
        self.llm_service_reader = llm_service_reader or (lambda: None)
        self.task_spawner = task_spawner or asyncio.create_task
        broker = stream_broker or GoalRuntimeSessionStreamBroker()
        self.session_runtime = GoalRuntimeSessionRuntime(
            store,
            registry,
            import_context,
            self.llm_service_reader,
            broker,
            session_context_reader=self.build_session_context_payload,
        )
        self.approval_runtime = GoalRuntimeApprovalRuntime(
            registry,
            self.session_runtime,
        )
        self._background_tasks: set[asyncio.Task] = set()

    async def _next_round_index(self, session_id: str) -> int:
        events = await self.store.get_agent_events(session_id)
        return max((int(item.get("round_index") or 0) for item in events), default=0) + 1

    @staticmethod
    def _initial_goal_json(message: str) -> dict:
        return {
            "message": message,
            "raw_message": message,
            "title": message,
            "last_message": message,
        }

    async def _prepare_session(
        self,
        session_id: str,
        message: str,
        permission_mode: str,
    ) -> int:
        session = await self.store.get_agent_session(session_id)
        if session is None:
            raise ValueError(f"session not found: {session_id}")
        if str(session.get("status") or "") in ACTIVE_SESSION_STATUSES:
            raise RuntimeError("session already has an active round")
        goal_json = dict(session.get("goal_json") or {})
        goal_json["last_message"] = message
        await self.store.update_agent_session_request(
            session_id,
            goal_json,
            permission_mode,
            "running",
            message,
            live_phase="planning",
        )
        return await self._next_round_index(session_id)

    async def _prepare_chat_session(
        self,
        session_id: str,
        message: str,
        permission_mode: str,
    ) -> int:
        session = await self.store.get_agent_session(session_id)
        if session is None:
            raise ValueError(f"session not found: {session_id}")
        if str(session.get("status") or "") in ACTIVE_SESSION_STATUSES:
            raise RuntimeError("session already has an active round")
        goal_json = dict(session.get("goal_json") or {})
        goal_json.setdefault("message", goal_json.get("raw_message") or message)
        goal_json.setdefault("raw_message", goal_json.get("message") or message)
        goal_json["last_message"] = message
        await self.store.update_agent_session_request(
            session_id,
            goal_json,
            permission_mode,
            "completed",
            message,
            live_phase="completed",
        )
        return await self._next_round_index(session_id)

    async def _append_chat_events(
        self,
        session_id: str,
        message: str,
        reply: str,
        *,
        round_index: int,
        reply_mode: str,
        suggestions: list[str] | None,
    ) -> None:
        await self.session_runtime.append_event(
            session_id,
            "UserMessageSubmitted",
            {"content": message},
            round_index=round_index,
            sequence=0,
            source="chat",
        )
        await self.session_runtime.append_event(
            session_id,
            "AssistantMessageGenerated",
            {
                "content": reply,
                "reply_mode": reply_mode,
                "suggestions": list(suggestions or ()),
            },
            round_index=round_index,
            sequence=1,
            source="chat",
        )

    async def build_session_context_payload(
        self,
        session_id: str,
        current_message: str,
    ) -> dict:
        return await load_session_context_payload(
            self.store,
            session_id,
            current_message,
        )

    async def append_event(
        self,
        session_id: str,
        event_type: str,
        payload: dict,
        **metadata,
    ) -> None:
        await self.session_runtime.append_event(
            session_id,
            event_type,
            payload,
            **metadata,
        )

    async def preview_session(self, message: str, permission_mode: str) -> dict:
        session_id = uuid4().hex
        goal_spec = await parse_goal_message(
            session_id,
            message,
            permission_mode,
            self.import_context,
            None,
        )
        plan = build_initial_plan(goal_spec, self.registry)
        return {
            "session_id": session_id,
            "status": "preview",
            "permission_mode": goal_spec.permission_mode,
            "summary": goal_spec.raw_message,
            "requires_approval": any(step.approval_required for step in plan.steps),
            "actions": [
                {
                    "step_id": step.step_id,
                    "capability_name": step.capability_name,
                    "arguments": dict(step.arguments),
                }
                for step in plan.steps
            ],
        }

    def _track_task(self, task: asyncio.Task) -> None:
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def wait_for_idle(self) -> None:
        if not self._background_tasks:
            return
        await asyncio.gather(*tuple(self._background_tasks))

    async def start_session(
        self,
        message: str,
        permission_mode: str,
        *,
        session_id: str = "",
    ) -> dict:
        session_key = str(session_id or "").strip() or uuid4().hex
        round_index = 1
        if session_id:
            round_index = await self._prepare_session(session_key, message, permission_mode)
        else:
            await self.store.create_agent_session(
                session_key,
                self._initial_goal_json(message),
                permission_mode,
                "running",
                message,
            )
        await self.session_runtime.append_event(
            session_key,
            "UserMessageSubmitted",
            {"content": message},
            round_index=round_index,
            sequence=0,
            source="chat",
        )
        task = self.task_spawner(
            self.session_runtime.run_session(
                session_key,
                message,
                permission_mode,
                round_index=round_index,
            )
        )
        self._track_task(task)
        return {
            "session_id": session_key,
            "status": "running",
            "live_phase": "planning",
            "permission_mode": permission_mode,
            "summary": message,
            "current_round": round_index,
            "requires_approval": False,
            "pending_approval": None,
            "event_types": [],
        }

    async def append_chat_turn(
        self,
        message: str,
        reply: str,
        permission_mode: str,
        *,
        session_id: str = "",
        reply_mode: str = "inline",
        suggestions: list[str] | None = None,
    ) -> dict:
        session_key = str(session_id or "").strip() or uuid4().hex
        if session_id:
            round_index = await self._prepare_chat_session(
                session_key,
                message,
                permission_mode,
            )
        else:
            await self.store.create_agent_session(
                session_key,
                self._initial_goal_json(message),
                permission_mode,
                "completed",
                message,
            )
            round_index = 1
        await self._append_chat_events(
            session_key,
            round_index=round_index,
            message=message,
            reply=reply,
            reply_mode=reply_mode,
            suggestions=suggestions,
        )
        await self.store.update_agent_session_status(
            session_key,
            "completed",
            message,
            live_phase="completed",
        )
        return {
            "session": await self.get_session(session_key),
            "events": await self.get_events(session_key),
        }

    async def resolve_approval(self, session_id: str, approved: bool) -> dict:
        return await self.approval_runtime.resolve_approval(session_id, approved)

    async def get_session(self, session_id: str) -> dict | None:
        return await self.session_runtime.get_session(session_id)

    async def list_sessions(self, limit: int = 20) -> list[dict]:
        return await self.store.list_agent_sessions(limit=limit)

    async def get_events(self, session_id: str) -> list[dict]:
        return await self.session_runtime.get_events(session_id)

    async def stream_session(self, session_id: str):
        async for item in self.session_runtime.stream_session(session_id):
            yield item

    async def delete_session(self, session_id: str) -> dict:
        session = await self.store.get_agent_session(session_id)
        if session is None:
            raise ValueError(f"session not found: {session_id}")
        if session.get("status") not in TERMINAL_SESSION_STATUSES:
            raise RuntimeError("running session cannot be deleted")
        await self.store.delete_agent_session(session_id)
        return {"session_id": session_id, "deleted": True}
