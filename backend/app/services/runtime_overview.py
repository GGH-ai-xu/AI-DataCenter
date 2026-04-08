from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.services.runtime_snapshot import (
    has_runtime_snapshot,
    snapshot_agent_health,
    snapshot_import_context,
)


HealthFallbackLoader = Callable[[], Awaitable[tuple[dict | None, dict]]]
ConnectionFactory = Callable[[dict | None], dict]


async def build_health_payload(
    *,
    runtime_status: dict,
    snapshot: dict | None,
    connection_factory: ConnectionFactory,
    llm_available: bool,
    llm_snapshot: dict[str, Any],
    ws_connections: int,
    fallback_loader: HealthFallbackLoader,
) -> dict[str, Any]:
    data_source = "cache"
    if has_runtime_snapshot(snapshot):
        agent_health = snapshot_agent_health(snapshot)
        import_context = snapshot_import_context(snapshot)
    else:
        agent_health, import_context = await fallback_loader()
        data_source = "realtime"

    return {
        "status": "ok",
        "agent_connected": agent_health is not None,
        "agent_info": agent_health,
        "ws_connections": ws_connections,
        "llm_available": llm_available,
        "connection": connection_factory(agent_health),
        "runtime": runtime_status,
        "import_context": import_context,
        "workspace_ready": bool(import_context.get("valid")),
        "llm": llm_snapshot,
        "data_source": data_source,
    }
