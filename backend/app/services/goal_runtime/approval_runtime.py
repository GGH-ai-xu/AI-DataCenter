from __future__ import annotations

from app.services.goal_runtime.executor import execute_capability


class GoalRuntimeApprovalRuntime:
    def __init__(self, registry, session_runtime) -> None:
        self.registry = registry
        self.session_runtime = session_runtime

    async def resolve_approval(self, session_id: str, approved: bool) -> dict:
        session = await self.session_runtime.get_session(session_id)
        if not session:
            raise ValueError(f"session not found: {session_id}")
        summary = session.get("summary", "")
        if not approved:
            await self.session_runtime.append_event(session_id, "ApprovalRejected", {})
            await self.session_runtime.complete_background_run(
                session_id,
                "aborted",
                summary,
            )
            return {"session_id": session_id, "status": "aborted"}

        actions = await self._load_pending_actions(session_id)
        await self.session_runtime.set_session_status(
            session_id,
            "running",
            summary,
            live_phase="executing",
        )
        await self.session_runtime.append_event(
            session_id,
            "ApprovalAccepted",
            {"actions": actions},
        )
        return await self._execute_actions(session_id, actions, summary)

    async def _execute_actions(
        self,
        session_id: str,
        actions: list[dict],
        summary: str,
    ) -> dict:
        for action in actions:
            await self.session_runtime.append_event(
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
                await self.session_runtime.append_event(
                    session_id,
                    "SessionFailed",
                    {
                        "step_id": action["step_id"],
                        "capability_name": action["capability_name"],
                        "error": result["error"],
                    },
                )
                await self.session_runtime.complete_background_run(
                    session_id,
                    "failed",
                    summary,
                )
                return {
                    "session_id": session_id,
                    "status": "failed",
                    "error": result["error"],
                }
            await self.session_runtime.append_event(
                session_id,
                "StepCompleted",
                {
                    "step_id": action["step_id"],
                    "capability_name": action["capability_name"],
                },
            )

        await self.session_runtime.append_event(
            session_id,
            "SessionCompleted",
            {"steps_completed": len(actions)},
        )
        await self.session_runtime.complete_background_run(
            session_id,
            "completed",
            summary,
        )
        return {"session_id": session_id, "status": "completed"}

    async def _load_pending_actions(self, session_id: str) -> list[dict]:
        events = await self.session_runtime.get_events(session_id)
        for event in reversed(events):
            if event.get("event_type") != "AwaitingApproval":
                continue
            actions = event.get("payload", {}).get("actions") or []
            if actions:
                return actions
        raise ValueError(f"no pending approval actions for session: {session_id}")
