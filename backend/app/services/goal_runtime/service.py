from __future__ import annotations

import asyncio
from uuid import uuid4

from app.services.goal_runtime.approval_runtime import GoalRuntimeApprovalRuntime
from app.services.goal_runtime.goal_parser import parse_goal_message
from app.services.goal_runtime.planner import build_initial_plan
from app.services.goal_runtime.session_runtime import GoalRuntimeSessionRuntime
from app.services.goal_runtime.session_stream import GoalRuntimeSessionStreamBroker


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
        )
        self.approval_runtime = GoalRuntimeApprovalRuntime(
            registry,
            self.session_runtime,
        )
        self._background_tasks: set[asyncio.Task] = set()

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

    async def start_session(self, message: str, permission_mode: str) -> dict:
        session_id = uuid4().hex
        await self.store.create_agent_session(
            session_id,
            {"message": message},
            permission_mode,
            "running",
            message,
        )
        task = self.task_spawner(
            self.session_runtime.run_session(session_id, message, permission_mode)
        )
        self._track_task(task)
        return {
            "session_id": session_id,
            "status": "running",
            "live_phase": "planning",
            "permission_mode": permission_mode,
            "summary": message,
            "requires_approval": False,
            "pending_approval": None,
            "event_types": [],
        }

    async def resolve_approval(self, session_id: str, approved: bool) -> dict:
        return await self.approval_runtime.resolve_approval(session_id, approved)

    async def get_session(self, session_id: str) -> dict | None:
        return await self.session_runtime.get_session(session_id)

    async def get_events(self, session_id: str) -> list[dict]:
        return await self.session_runtime.get_events(session_id)

    async def stream_session(self, session_id: str):
        async for item in self.session_runtime.stream_session(session_id):
            yield item
