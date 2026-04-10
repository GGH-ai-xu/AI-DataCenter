from __future__ import annotations

import json
import time
from typing import Any

import aiosqlite

from app.services.cluster_control.models import JobSpecRecord


CLUSTER_CONTROL_INIT_SQL = """
CREATE TABLE IF NOT EXISTS cluster_nodes (
    node_id TEXT PRIMARY KEY,
    cluster_id TEXT NOT NULL,
    label TEXT NOT NULL,
    state TEXT NOT NULL,
    execution_backend TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS cluster_devices (
    device_id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL,
    device_type TEXT NOT NULL,
    device_index INTEGER NOT NULL,
    pci_bus_id TEXT NOT NULL DEFAULT '',
    memory_bytes INTEGER NOT NULL DEFAULT 0,
    attributes_json TEXT NOT NULL DEFAULT '{}',
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS cluster_queues (
    queue_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    state TEXT NOT NULL,
    default_priority INTEGER NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS cluster_jobs (
    job_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    queue_id TEXT NOT NULL,
    submitter_id TEXT NOT NULL,
    job_type TEXT NOT NULL,
    entrypoint TEXT NOT NULL,
    args_json TEXT NOT NULL,
    env_json TEXT NOT NULL,
    resource_request_json TEXT NOT NULL,
    placement_constraints_json TEXT NOT NULL,
    priority INTEGER NOT NULL,
    preemptible INTEGER NOT NULL,
    max_retries INTEGER NOT NULL,
    timeout_seconds INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    execution_backend TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cluster_jobs_queue_status
    ON cluster_jobs(queue_id, status, priority DESC, created_at ASC);

CREATE TABLE IF NOT EXISTS cluster_reservations (
    reservation_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    device_ids_json TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS cluster_allocations (
    allocation_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    reservation_id TEXT NOT NULL DEFAULT '',
    node_id TEXT NOT NULL,
    gpu_bindings_json TEXT NOT NULL,
    status TEXT NOT NULL,
    execution_backend TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cluster_allocations_job_status
    ON cluster_allocations(job_id, status, created_at DESC);
"""


def require_cluster_db(
    connection: aiosqlite.Connection | None,
) -> aiosqlite.Connection:
    if connection is None:
        raise RuntimeError("data store has not been initialized")
    return connection


def _loads_json(value: str, fallback: Any) -> Any:
    if not value:
        return fallback
    return json.loads(value)


def _dumps_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _normalize_job(row: aiosqlite.Row | None) -> dict | None:
    if row is None:
        return None
    item = dict(row)
    item["args"] = _loads_json(item.pop("args_json"), [])
    item["env"] = _loads_json(item.pop("env_json"), {})
    item["resource_request"] = _loads_json(item.pop("resource_request_json"), {})
    item["placement_constraints"] = _loads_json(
        item.pop("placement_constraints_json"),
        {},
    )
    item["preemptible"] = bool(item["preemptible"])
    return item


def _normalize_allocation(row: aiosqlite.Row) -> dict:
    item = dict(row)
    item["gpu_bindings"] = _loads_json(item["gpu_bindings_json"], [])
    return item


async def upsert_queue(connection: aiosqlite.Connection, payload: dict) -> None:
    now = time.time()
    await connection.execute(
        """INSERT INTO cluster_queues
           (queue_id, name, state, default_priority, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(queue_id) DO UPDATE SET
               name = excluded.name,
               state = excluded.state,
               default_priority = excluded.default_priority,
               updated_at = excluded.updated_at""",
        (
            payload["queue_id"],
            payload["name"],
            payload["state"],
            int(payload["default_priority"]),
            now,
            now,
        ),
    )
    await connection.commit()


async def list_queues(connection: aiosqlite.Connection) -> list[dict]:
    cursor = await connection.execute(
        """SELECT queue_id, name, state, default_priority, created_at, updated_at
           FROM cluster_queues
           ORDER BY default_priority DESC, queue_id ASC"""
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def create_job(
    connection: aiosqlite.Connection,
    record: JobSpecRecord,
) -> None:
    now = time.time()
    await connection.execute(
        """INSERT INTO cluster_jobs
           (job_id, tenant_id, project_id, queue_id, submitter_id, job_type,
            entrypoint, args_json, env_json, resource_request_json,
            placement_constraints_json, priority, preemptible, max_retries,
            timeout_seconds, status, execution_backend, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            record.job_id,
            record.tenant_id,
            record.project_id,
            record.queue_id,
            record.submitter_id,
            record.job_type,
            record.entrypoint,
            _dumps_json(list(record.args)),
            _dumps_json(dict(record.env)),
            _dumps_json(dict(record.resource_request)),
            _dumps_json(dict(record.placement_constraints)),
            record.priority,
            1 if record.preemptible else 0,
            record.max_retries,
            record.timeout_seconds,
            "queued",
            "",
            now,
            now,
        ),
    )
    await connection.commit()


async def get_job(
    connection: aiosqlite.Connection,
    job_id: str,
) -> dict | None:
    cursor = await connection.execute(
        "SELECT * FROM cluster_jobs WHERE job_id = ?",
        (job_id,),
    )
    return _normalize_job(await cursor.fetchone())


async def list_jobs(connection: aiosqlite.Connection) -> list[dict]:
    cursor = await connection.execute(
        """SELECT * FROM cluster_jobs
           ORDER BY created_at DESC, job_id DESC"""
    )
    rows = await cursor.fetchall()
    return [_normalize_job(row) for row in rows if row is not None]


async def update_job_state(
    connection: aiosqlite.Connection,
    job_id: str,
    status: str,
    *,
    execution_backend: str = "",
) -> None:
    await connection.execute(
        """UPDATE cluster_jobs
           SET status = ?, execution_backend = ?, updated_at = ?
           WHERE job_id = ?""",
        (
            status,
            execution_backend,
            time.time(),
            job_id,
        ),
    )
    await connection.commit()


async def create_allocation(
    connection: aiosqlite.Connection,
    payload: dict,
) -> None:
    now = time.time()
    await connection.execute(
        """INSERT INTO cluster_allocations
           (allocation_id, job_id, reservation_id, node_id, gpu_bindings_json,
            status, execution_backend, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            payload["allocation_id"],
            payload["job_id"],
            payload.get("reservation_id", ""),
            payload["node_id"],
            payload["gpu_bindings_json"],
            payload["status"],
            payload["execution_backend"],
            now,
            now,
        ),
    )
    await connection.commit()


async def list_allocations(connection: aiosqlite.Connection) -> list[dict]:
    cursor = await connection.execute(
        """SELECT * FROM cluster_allocations
           ORDER BY created_at DESC, allocation_id DESC"""
    )
    rows = await cursor.fetchall()
    return [_normalize_allocation(row) for row in rows]
