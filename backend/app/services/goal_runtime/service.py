from __future__ import annotations

from uuid import uuid4

from app.services.goal_runtime.executor import execute_capability
from app.services.goal_runtime.goal_parser import parse_goal_message
from app.services.goal_runtime.planner import build_initial_plan
from app.services.goal_runtime.reasoning_trace import build_reasoning_trace
from app.services.goal_runtime.session_events import build_goal_parsed_event
from app.services.goal_runtime.supervisor import execute_plan_session


class GoalRuntimeService:
    def __init__(
        self,
        store,
        registry,
        import_context,
        runtime_status_reader,
        llm_service_reader=None,
    ) -> None:
        self.store = store
        self.registry = registry
        self.import_context = import_context
        self.runtime_status_reader = runtime_status_reader
        self.llm_service_reader = llm_service_reader or (lambda: None)

    async def append_event(
        self,
        session_id: str,
        event_type: str,
        payload: dict,
        **metadata,
    ) -> None:
        await self.store.append_agent_event(
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

    async def start_session(self, message: str, permission_mode: str) -> dict:
        session_id = uuid4().hex
        planning_result, trace_events = await build_reasoning_trace(
            message=message,
            permission_mode=permission_mode,
            registry=self.registry,
            llm_service=self.llm_service_reader(),
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
        await self.store.create_agent_session(
            session_id,
            {"message": message},
            goal_spec.permission_mode,
            "running",
            goal_spec.raw_message,
        )
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
            sequence=len(trace_events) + 1,
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
            sequence=len(trace_events) + 2,
            source="planner",
        )
        result = await execute_plan_session(
            session_id,
            goal_spec,
            plan,
            self.registry,
            self,
        )
        await self.store.update_agent_session_status(
            session_id,
            result["status"],
            goal_spec.raw_message,
        )
        return {
            "session_id": session_id,
            "status": result["status"],
            "permission_mode": goal_spec.permission_mode,
            "summary": goal_spec.raw_message,
            "requires_approval": result["status"] == "awaiting_approval",
            "pending_approval": result.get("pending_approval"),
            "event_types": result.get("event_types", []),
        }

    async def resolve_approval(self, session_id: str, approved: bool) -> dict:
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"session not found: {session_id}")
        if not approved:
            await self.append_event(session_id, "ApprovalRejected", {})
            await self.store.update_agent_session_status(
                session_id,
                "aborted",
                session.get("summary", ""),
            )
            return {"session_id": session_id, "status": "aborted"}

        actions = await self._load_pending_actions(session_id)
        await self.append_event(session_id, "ApprovalAccepted", {"actions": actions})
        for action in actions:
            await self.append_event(
                session_id,
                "StepStarted",
                {
                    "step_id": action["step_id"],
                    "capability_name": action["capability_name"],
                },
            )
            result = await execute_capability(
                self.registry,
                action["capability_name"],
                {},
                dict(action.get("arguments") or {}),
            )
            if not result["success"]:
                await self.append_event(
                    session_id,
                    "SessionFailed",
                    {
                        "step_id": action["step_id"],
                        "capability_name": action["capability_name"],
                        "error": result["error"],
                    },
                )
                await self.store.update_agent_session_status(
                    session_id,
                    "failed",
                    session.get("summary", ""),
                )
                return {
                    "session_id": session_id,
                    "status": "failed",
                    "error": result["error"],
                }
            await self.append_event(
                session_id,
                "StepCompleted",
                {
                    "step_id": action["step_id"],
                    "capability_name": action["capability_name"],
                },
            )

        await self.append_event(
            session_id,
            "SessionCompleted",
            {"steps_completed": len(actions)},
        )
        await self.store.update_agent_session_status(
            session_id,
            "completed",
            session.get("summary", ""),
        )
        return {"session_id": session_id, "status": "completed"}

    async def get_session(self, session_id: str) -> dict | None:
        return await self.store.get_agent_session(session_id)

    async def get_events(self, session_id: str) -> list[dict]:
        return await self.store.get_agent_events(session_id)

    async def _load_pending_actions(self, session_id: str) -> list[dict]:
        events = await self.get_events(session_id)
        for event in reversed(events):
            if event.get("event_type") != "AwaitingApproval":
                continue
            actions = event.get("payload", {}).get("actions") or []
            if actions:
                return actions
        raise ValueError(f"no pending approval actions for session: {session_id}")
