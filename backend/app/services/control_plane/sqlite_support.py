from __future__ import annotations

import json
import time
from typing import Any

import aiosqlite

from app.services.control_plane.models import ControlCommandRecord


CONTROL_PLANE_INIT_SQL = """
CREATE TABLE IF NOT EXISTS control_commands (
    command_id TEXT PRIMARY KEY,
    capability_name TEXT NOT NULL,
    domain TEXT NOT NULL,
    operator_id TEXT NOT NULL,
    operator_type TEXT NOT NULL,
    workspace_key TEXT NOT NULL,
    source_page TEXT NOT NULL,
    arguments_json TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    permission_mode TEXT NOT NULL,
    approval_state TEXT NOT NULL,
    execution_state TEXT NOT NULL,
    result_summary TEXT NOT NULL DEFAULT '',
    error_message TEXT NOT NULL DEFAULT '',
    related_session_id TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_control_commands_workspace_created
    ON control_commands(workspace_key, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_control_commands_created_at
    ON control_commands(created_at DESC);
"""

UPDATABLE_FIELDS = frozenset(
    {
        "approval_state",
        "execution_state",
        "result_summary",
        "error_message",
        "related_session_id",
    }
)


def require_control_plane_db(
    connection: aiosqlite.Connection | None,
) -> aiosqlite.Connection:
    if connection is None:
        raise RuntimeError("data store has not been initialized")
    return connection


def _dumps_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _loads_json(value: str) -> dict:
    if not value:
        return {}
    return dict(json.loads(value))


def _normalize_command(row: aiosqlite.Row | None) -> dict | None:
    if row is None:
        return None
    item = dict(row)
    item["arguments"] = _loads_json(item.pop("arguments_json"))
    return item


async def create_command(
    connection: aiosqlite.Connection,
    record: ControlCommandRecord,
) -> None:
    now = time.time()
    await connection.execute(
        """INSERT INTO control_commands
           (command_id, capability_name, domain, operator_id, operator_type,
            workspace_key, source_page, arguments_json, risk_level,
            permission_mode, approval_state, execution_state, result_summary,
            error_message, related_session_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            record.command_id,
            record.capability_name,
            record.domain,
            record.operator_id,
            record.operator_type,
            record.workspace_key,
            record.source_page,
            _dumps_json(record.arguments),
            record.risk_level,
            record.permission_mode,
            record.approval_state,
            record.execution_state,
            record.result_summary,
            record.error_message,
            record.related_session_id,
            now,
            now,
        ),
    )
    await connection.commit()


async def get_command(
    connection: aiosqlite.Connection,
    command_id: str,
) -> dict | None:
    cursor = await connection.execute(
        "SELECT * FROM control_commands WHERE command_id = ?",
        (command_id,),
    )
    return _normalize_command(await cursor.fetchone())


async def list_commands(
    connection: aiosqlite.Connection,
    *,
    workspace_key: str | None = None,
    limit: int = 20,
) -> list[dict]:
    if workspace_key:
        cursor = await connection.execute(
            """SELECT * FROM control_commands
               WHERE workspace_key = ?
               ORDER BY created_at DESC, command_id DESC
               LIMIT ?""",
            (workspace_key, limit),
        )
    else:
        cursor = await connection.execute(
            """SELECT * FROM control_commands
               ORDER BY created_at DESC, command_id DESC
               LIMIT ?""",
            (limit,),
        )
    rows = await cursor.fetchall()
    return [_normalize_command(row) for row in rows if row is not None]


async def update_command(
    connection: aiosqlite.Connection,
    command_id: str,
    changes: dict[str, Any],
) -> None:
    normalized = {
        key: value
        for key, value in changes.items()
        if key in UPDATABLE_FIELDS
    }
    if not normalized:
        return
    assignments = ", ".join(f"{key} = ?" for key in normalized)
    values = [normalized[key] or "" for key in normalized]
    values.extend((time.time(), command_id))
    await connection.execute(
        f"""UPDATE control_commands
            SET {assignments}, updated_at = ?
            WHERE command_id = ?""",
        tuple(values),
    )
    await connection.commit()
