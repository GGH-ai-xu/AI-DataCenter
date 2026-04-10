from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.models.schemas import (
    AgentRuntimeApprovalRequest,
    AgentRuntimeStartRequest,
)
from app.services.sse import encode_sse_event


router = APIRouter(prefix="/api/agent-runtime", tags=["Agent Runtime"])


@router.post("/sessions")
async def start_agent_runtime_session(req: AgentRuntimeStartRequest):
    from app.main import app_state

    return await app_state.goal_runtime.start_session(
        req.message,
        req.permission_mode,
    )


@router.get("/sessions")
async def list_agent_runtime_sessions(
    limit: int = Query(default=20, ge=1, le=100),
):
    from app.main import app_state

    return {"sessions": await app_state.goal_runtime.list_sessions(limit=limit)}


@router.post("/sessions/{session_id}/approve")
async def approve_agent_runtime_session(
    session_id: str,
    req: AgentRuntimeApprovalRequest,
):
    from app.main import app_state

    try:
        return await app_state.goal_runtime.resolve_approval(
            session_id,
            req.approved,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/sessions/{session_id}")
async def delete_agent_runtime_session(session_id: str):
    from app.main import app_state

    try:
        return await app_state.goal_runtime.delete_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/sessions/{session_id}")
async def get_agent_runtime_session(session_id: str):
    from app.main import app_state

    session = await app_state.goal_runtime.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return session


@router.get("/sessions/{session_id}/events")
async def get_agent_runtime_events(session_id: str):
    from app.main import app_state

    session = await app_state.goal_runtime.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {"events": await app_state.goal_runtime.get_events(session_id)}


@router.get("/sessions/{session_id}/stream")
async def stream_agent_runtime_session(session_id: str):
    from app.main import app_state

    session = await app_state.goal_runtime.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    async def iterator():
        async for item in app_state.goal_runtime.stream_session(session_id):
            yield encode_sse_event(item["event"], item["data"])

    return StreamingResponse(iterator(), media_type="text/event-stream")
