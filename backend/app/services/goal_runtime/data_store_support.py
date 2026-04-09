from __future__ import annotations

import json
import time
from typing import Any

import aiosqlite


GOAL_RUNTIME_INIT_SQL = """
CREATE TABLE IF NOT EXISTS agent_runtime_sessions (
    session_id TEXT PRIMARY KEY,
    goal_json TEXT NOT NULL,
    permission_mode TEXT NOT NULL,
    status TEXT NOT NULL,
    live_phase TEXT NOT NULL DEFAULT 'planning',
    summary TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_runtime_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    round_index INTEGER NOT NULL DEFAULT 0,
    sequence INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'runtime',
    duration_ms INTEGER NOT NULL DEFAULT 0,
    timestamp REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_runtime_events_session_ts
    ON agent_runtime_events(session_id, timestamp);

CREATE TABLE IF NOT EXISTS agent_runtime_stream_state (
    session_id TEXT NOT NULL,
    stream_kind TEXT NOT NULL,
    latest_text TEXT NOT NULL DEFAULT '',
    latest_char_count INTEGER NOT NULL DEFAULT 0,
    revision INTEGER NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL,
    PRIMARY KEY (session_id, stream_kind)
);
"""

RUNTIME_SESSION_COLUMN_STATEMENTS = {
    "live_phase": (
        "ALTER TABLE agent_runtime_sessions "
        "ADD COLUMN live_phase TEXT NOT NULL DEFAULT 'planning'"
    ),
}

RUNTIME_EVENT_COLUMN_STATEMENTS = {
    "round_index": "ALTER TABLE agent_runtime_events ADD COLUMN round_index INTEGER NOT NULL DEFAULT 0",
    "sequence": "ALTER TABLE agent_runtime_events ADD COLUMN sequence INTEGER NOT NULL DEFAULT 0",
    "source": "ALTER TABLE agent_runtime_events ADD COLUMN source TEXT NOT NULL DEFAULT 'runtime'",
    "duration_ms": "ALTER TABLE agent_runtime_events ADD COLUMN duration_ms INTEGER NOT NULL DEFAULT 0",
}


def require_runtime_db(
    connection: aiosqlite.Connection | None,
) -> aiosqlite.Connection:
    if connection is None:
        raise RuntimeError("data store has not been initialized")
    return connection


def _loads_json(value: str, fallback: Any) -> Any:
    if not value:
        return fallback
    return json.loads(value)


def _normalize_session(row: aiosqlite.Row | None) -> dict | None:
    if row is None:
        return None
    item = dict(row)
    item["goal_json"] = _loads_json(item["goal_json"], {})
    return item


def _normalize_event(row: aiosqlite.Row) -> dict:
    item = dict(row)
    item["payload"] = _loads_json(item.pop("payload_json"), {})
    return item


async def ensure_runtime_session_columns(
    connection: aiosqlite.Connection,
) -> None:
    cursor = await connection.execute("PRAGMA table_info(agent_runtime_sessions)")
    rows = await cursor.fetchall()
    existing_columns = {str(row[1]) for row in rows}
    for column_name, statement in RUNTIME_SESSION_COLUMN_STATEMENTS.items():
        if column_name in existing_columns:
            continue
        await connection.execute(statement)


async def create_agent_session(
    connection: aiosqlite.Connection,
    session_id: str,
    goal_json: dict,
    permission_mode: str,
    status: str,
    summary: str,
) -> None:
    now = time.time()
    await connection.execute(
        """INSERT INTO agent_runtime_sessions
           (session_id, goal_json, permission_mode, status, live_phase, summary, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            session_id,
            json.dumps(goal_json, ensure_ascii=False),
            permission_mode,
            status,
            "planning",
            summary,
            now,
            now,
        ),
    )
    await connection.commit()


async def ensure_runtime_event_columns(
    connection: aiosqlite.Connection,
) -> None:
    cursor = await connection.execute("PRAGMA table_info(agent_runtime_events)")
    rows = await cursor.fetchall()
    existing_columns = {str(row[1]) for row in rows}
    for column_name, statement in RUNTIME_EVENT_COLUMN_STATEMENTS.items():
        if column_name in existing_columns:
            continue
        await connection.execute(statement)


async def update_agent_session_status(
    connection: aiosqlite.Connection,
    session_id: str,
    status: str,
    summary: str,
    *,
    live_phase: str | None = None,
) -> None:
    if live_phase is None:
        await connection.execute(
            """UPDATE agent_runtime_sessions
               SET status = ?, summary = ?, updated_at = ?
               WHERE session_id = ?""",
            (status, summary, time.time(), session_id),
        )
    else:
        await connection.execute(
            """UPDATE agent_runtime_sessions
               SET status = ?, live_phase = ?, summary = ?, updated_at = ?
               WHERE session_id = ?""",
            (status, live_phase, summary, time.time(), session_id),
        )
    await connection.commit()


async def get_agent_session(
    connection: aiosqlite.Connection,
    session_id: str,
) -> dict | None:
    cursor = await connection.execute(
        "SELECT * FROM agent_runtime_sessions WHERE session_id = ?",
        (session_id,),
    )
    return _normalize_session(await cursor.fetchone())


async def append_agent_event(
    connection: aiosqlite.Connection,
    session_id: str,
    event_type: str,
    payload: dict,
    *,
    round_index: int = 0,
    sequence: int = 0,
    source: str = "runtime",
    duration_ms: int = 0,
) -> None:
    await connection.execute(
        """INSERT INTO agent_runtime_events
           (session_id, event_type, payload_json, round_index, sequence, source, duration_ms, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            session_id,
            event_type,
            json.dumps(payload, ensure_ascii=False),
            round_index,
            sequence,
            source,
            duration_ms,
            time.time(),
        ),
    )
    await connection.commit()


async def upsert_agent_stream_state(
    connection: aiosqlite.Connection,
    session_id: str,
    stream_kind: str,
    *,
    latest_text: str,
    latest_char_count: int,
    revision: int,
) -> None:
    await connection.execute(
        """INSERT INTO agent_runtime_stream_state
           (session_id, stream_kind, latest_text, latest_char_count, revision, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(session_id, stream_kind) DO UPDATE SET
             latest_text = excluded.latest_text,
             latest_char_count = excluded.latest_char_count,
             revision = excluded.revision,
             updated_at = excluded.updated_at""",
        (
            session_id,
            stream_kind,
            latest_text,
            latest_char_count,
            revision,
            time.time(),
        ),
    )
    await connection.commit()


async def get_agent_stream_state(
    connection: aiosqlite.Connection,
    session_id: str,
    stream_kind: str,
) -> dict | None:
    cursor = await connection.execute(
        """SELECT session_id, stream_kind, latest_text, latest_char_count, revision, updated_at
           FROM agent_runtime_stream_state
           WHERE session_id = ? AND stream_kind = ?""",
        (session_id, stream_kind),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_agent_events(
    connection: aiosqlite.Connection,
    session_id: str,
) -> list[dict]:
    cursor = await connection.execute(
        """SELECT id, session_id, event_type, payload_json, round_index,
                  sequence, source, duration_ms, timestamp
           FROM agent_runtime_events
           WHERE session_id = ?
           ORDER BY id ASC""",
        (session_id,),
    )
    rows = await cursor.fetchall()
    return [_normalize_event(row) for row in rows]
