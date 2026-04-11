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
    drain_state TEXT NOT NULL DEFAULT 'active',
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
    max_concurrency INTEGER NOT NULL DEFAULT 0,
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
    task_kind TEXT NOT NULL DEFAULT 'batch_compute',
    lifecycle_kind TEXT NOT NULL DEFAULT 'batch',
    entrypoint TEXT NOT NULL,
    args_json TEXT NOT NULL,
    env_json TEXT NOT NULL,
    resource_request_json TEXT NOT NULL,
    placement_constraints_json TEXT NOT NULL,
    service_ports_json TEXT NOT NULL DEFAULT '[]',
    checkpoint_policy TEXT NOT NULL DEFAULT 'none',
    runtime_profile_json TEXT NOT NULL DEFAULT '{}',
    priority INTEGER NOT NULL,
    preemptible INTEGER NOT NULL,
    max_retries INTEGER NOT NULL,
    timeout_seconds INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    execution_backend TEXT NOT NULL DEFAULT '',
    last_plan_type TEXT NOT NULL DEFAULT '',
    last_plan_reason TEXT NOT NULL DEFAULT '',
    last_error TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL DEFAULT '',
    checkpoint_status TEXT NOT NULL DEFAULT '',
    checkpoint_manifest_path TEXT NOT NULL DEFAULT '',
    checkpoint_error TEXT NOT NULL DEFAULT '',
    checkpoint_updated_at REAL NOT NULL DEFAULT 0,
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
    runtime_job_handle TEXT NOT NULL DEFAULT '',
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
    item["service_ports"] = _loads_json(item.pop("service_ports_json"), [])
    item["runtime_profile"] = _loads_json(item.pop("runtime_profile_json"), {})
    item["preemptible"] = bool(item["preemptible"])
    return item


def _normalize_allocation(row: aiosqlite.Row) -> dict:
    item = dict(row)
    item["gpu_bindings"] = _loads_json(item["gpu_bindings_json"], [])
    item["runtime_job_handle"] = str(item.get("runtime_job_handle") or "")
    return item


def _normalize_queue(row: aiosqlite.Row | None) -> dict | None:
    if row is None:
        return None
    item = dict(row)
    item["default_priority"] = int(item.get("default_priority") or 0)
    item["max_concurrency"] = int(item.get("max_concurrency") or 0)
    return item


def _normalize_node(row: aiosqlite.Row | None) -> dict | None:
    if row is None:
        return None
    item = dict(row)
    item["metadata"] = _loads_json(item.pop("metadata_json"), {})
    return item


async def ensure_cluster_tables(connection: aiosqlite.Connection) -> None:
    statements = (
        "ALTER TABLE cluster_nodes ADD COLUMN drain_state TEXT NOT NULL DEFAULT 'active'",
        "ALTER TABLE cluster_queues ADD COLUMN max_concurrency INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE cluster_jobs ADD COLUMN task_kind TEXT NOT NULL DEFAULT 'batch_compute'",
        "ALTER TABLE cluster_jobs ADD COLUMN lifecycle_kind TEXT NOT NULL DEFAULT 'batch'",
        "ALTER TABLE cluster_jobs ADD COLUMN service_ports_json TEXT NOT NULL DEFAULT '[]'",
        "ALTER TABLE cluster_jobs ADD COLUMN checkpoint_policy TEXT NOT NULL DEFAULT 'none'",
        "ALTER TABLE cluster_jobs ADD COLUMN runtime_profile_json TEXT NOT NULL DEFAULT '{}'",
        "ALTER TABLE cluster_jobs ADD COLUMN last_plan_type TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE cluster_jobs ADD COLUMN last_plan_reason TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE cluster_jobs ADD COLUMN last_error TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE cluster_jobs ADD COLUMN checkpoint_id TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE cluster_jobs ADD COLUMN checkpoint_status TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE cluster_jobs ADD COLUMN checkpoint_manifest_path TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE cluster_jobs ADD COLUMN checkpoint_error TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE cluster_jobs ADD COLUMN checkpoint_updated_at REAL NOT NULL DEFAULT 0",
        "ALTER TABLE cluster_allocations ADD COLUMN runtime_job_handle TEXT NOT NULL DEFAULT ''",
    )
    for statement in statements:
        try:
            await connection.execute(statement)
        except aiosqlite.OperationalError:
            continue
    await connection.commit()


async def upsert_node(connection: aiosqlite.Connection, payload: dict) -> None:
    await connection.execute(
        """INSERT INTO cluster_nodes
           (node_id, cluster_id, label, state, drain_state, execution_backend, metadata_json, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(node_id) DO UPDATE SET
               cluster_id = excluded.cluster_id,
               label = excluded.label,
               state = excluded.state,
               drain_state = excluded.drain_state,
               execution_backend = excluded.execution_backend,
               metadata_json = excluded.metadata_json,
               updated_at = excluded.updated_at""",
        (
            payload["node_id"],
            payload["cluster_id"],
            payload["label"],
            payload["state"],
            payload.get("drain_state", "active"),
            payload["execution_backend"],
            _dumps_json(payload.get("metadata", {})),
            time.time(),
        ),
    )
    await connection.commit()


async def get_node(connection: aiosqlite.Connection, node_id: str) -> dict | None:
    cursor = await connection.execute(
        "SELECT * FROM cluster_nodes WHERE node_id = ?",
        (node_id,),
    )
    return _normalize_node(await cursor.fetchone())


async def list_nodes(connection: aiosqlite.Connection) -> list[dict]:
    cursor = await connection.execute(
        """SELECT * FROM cluster_nodes
           ORDER BY node_id ASC"""
    )
    rows = await cursor.fetchall()
    return [_normalize_node(row) for row in rows if row is not None]


async def update_node_drain_state(
    connection: aiosqlite.Connection,
    node_id: str,
    drain_state: str,
) -> None:
    await connection.execute(
        """UPDATE cluster_nodes
           SET drain_state = ?, updated_at = ?
           WHERE node_id = ?""",
        (drain_state, time.time(), node_id),
    )
    await connection.commit()


async def upsert_queue(connection: aiosqlite.Connection, payload: dict) -> None:
    now = time.time()
    await connection.execute(
        """INSERT INTO cluster_queues
           (queue_id, name, state, default_priority, max_concurrency, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(queue_id) DO UPDATE SET
               name = excluded.name,
               state = excluded.state,
               default_priority = excluded.default_priority,
               max_concurrency = excluded.max_concurrency,
               updated_at = excluded.updated_at""",
        (
            payload["queue_id"],
            payload["name"],
            payload["state"],
            int(payload["default_priority"]),
            int(payload.get("max_concurrency") or 0),
            now,
            now,
        ),
    )
    await connection.commit()


async def get_queue(connection: aiosqlite.Connection, queue_id: str) -> dict | None:
    cursor = await connection.execute(
        """SELECT queue_id, name, state, default_priority, max_concurrency, created_at, updated_at
           FROM cluster_queues
           WHERE queue_id = ?""",
        (queue_id,),
    )
    return _normalize_queue(await cursor.fetchone())


async def list_queues(connection: aiosqlite.Connection) -> list[dict]:
    cursor = await connection.execute(
        """SELECT queue_id, name, state, default_priority, max_concurrency, created_at, updated_at
           FROM cluster_queues
           ORDER BY default_priority DESC, queue_id ASC"""
    )
    rows = await cursor.fetchall()
    return [_normalize_queue(row) for row in rows if row is not None]


async def create_job(
    connection: aiosqlite.Connection,
    record: JobSpecRecord,
) -> None:
    now = time.time()
    await connection.execute(
        """INSERT INTO cluster_jobs
           (job_id, tenant_id, project_id, queue_id, submitter_id, job_type,
            task_kind, lifecycle_kind, entrypoint, args_json, env_json,
            resource_request_json, placement_constraints_json, service_ports_json,
           checkpoint_policy, runtime_profile_json, priority, preemptible,
           max_retries, timeout_seconds, status, execution_backend, last_plan_type,
           last_plan_reason, last_error, checkpoint_id, checkpoint_status,
           checkpoint_manifest_path, checkpoint_error, checkpoint_updated_at,
           created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            record.job_id,
            record.tenant_id,
            record.project_id,
            record.queue_id,
            record.submitter_id,
            record.job_type,
            record.task_kind,
            record.lifecycle_kind,
            record.entrypoint,
            _dumps_json(list(record.args)),
            _dumps_json(dict(record.env)),
            _dumps_json(dict(record.resource_request)),
            _dumps_json(dict(record.placement_constraints)),
            _dumps_json(list(record.service_ports)),
            record.checkpoint_policy,
            _dumps_json(dict(record.runtime_profile)),
            record.priority,
            1 if record.preemptible else 0,
            record.max_retries,
            record.timeout_seconds,
            "queued",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            0,
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
    plan_type: str | None = None,
    plan_reason: str | None = None,
    last_error: str | None = None,
) -> None:
    assignments = ["status = ?", "execution_backend = ?", "updated_at = ?"]
    params: list[Any] = [status, execution_backend, time.time()]
    if plan_type is not None:
        assignments.append("last_plan_type = ?")
        params.append(plan_type)
    if plan_reason is not None:
        assignments.append("last_plan_reason = ?")
        params.append(plan_reason)
    if last_error is not None:
        assignments.append("last_error = ?")
        params.append(last_error)
    params.append(job_id)
    await connection.execute(
        f"""UPDATE cluster_jobs
           SET {", ".join(assignments)}
           WHERE job_id = ?""",
        tuple(params),
    )
    await connection.commit()


async def update_job_checkpoint(
    connection: aiosqlite.Connection,
    job_id: str,
    changes: dict,
) -> None:
    assignments = ["updated_at = ?"]
    params: list[Any] = [time.time()]
    fields = (
        "checkpoint_id",
        "checkpoint_status",
        "checkpoint_manifest_path",
        "checkpoint_error",
        "checkpoint_updated_at",
    )
    for field in fields:
        if field not in changes:
            continue
        assignments.append(f"{field} = ?")
        params.append(changes[field])
    params.append(job_id)
    await connection.execute(
        f"""UPDATE cluster_jobs
           SET {", ".join(assignments)}
           WHERE job_id = ?""",
        tuple(params),
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
            runtime_job_handle, status, execution_backend, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            payload["allocation_id"],
            payload["job_id"],
            payload.get("reservation_id", ""),
            payload["node_id"],
            payload["gpu_bindings_json"],
            str(payload.get("runtime_job_handle") or ""),
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


async def get_allocation(
    connection: aiosqlite.Connection,
    allocation_id: str,
) -> dict | None:
    cursor = await connection.execute(
        "SELECT * FROM cluster_allocations WHERE allocation_id = ?",
        (allocation_id,),
    )
    row = await cursor.fetchone()
    return _normalize_allocation(row) if row is not None else None


async def update_allocations_for_job(
    connection: aiosqlite.Connection,
    job_id: str,
    status: str,
) -> None:
    await connection.execute(
        """UPDATE cluster_allocations
           SET status = ?, updated_at = ?
           WHERE job_id = ?""",
        (
            status,
            time.time(),
            job_id,
        ),
    )
    await connection.commit()


async def release_allocation(
    connection: aiosqlite.Connection,
    allocation_id: str,
) -> None:
    await connection.execute(
        """UPDATE cluster_allocations
           SET status = ?, updated_at = ?
           WHERE allocation_id = ?""",
        ("released", time.time(), allocation_id),
    )
    await connection.commit()
