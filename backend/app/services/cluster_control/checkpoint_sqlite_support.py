from __future__ import annotations

import time

import aiosqlite


CLUSTER_CHECKPOINT_INIT_SQL = """
CREATE TABLE IF NOT EXISTS cluster_checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    allocation_id TEXT NOT NULL DEFAULT '',
    node_id TEXT NOT NULL DEFAULT '',
    runtime_job_handle TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    manifest_path TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cluster_checkpoints_job_updated
    ON cluster_checkpoints(job_id, updated_at DESC, checkpoint_id DESC);

CREATE INDEX IF NOT EXISTS idx_cluster_checkpoints_job_status_updated
    ON cluster_checkpoints(job_id, status, updated_at DESC, checkpoint_id DESC);
"""


def _normalize_checkpoint(row: aiosqlite.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


async def ensure_cluster_checkpoint_tables(connection: aiosqlite.Connection) -> None:
    await connection.executescript(CLUSTER_CHECKPOINT_INIT_SQL)
    await connection.execute(
        """INSERT OR IGNORE INTO cluster_checkpoints
           (checkpoint_id, job_id, allocation_id, node_id, runtime_job_handle,
            status, manifest_path, error, created_at, updated_at)
           SELECT checkpoint_id,
                  job_id,
                  '',
                  '',
                  '',
                  checkpoint_status,
                  checkpoint_manifest_path,
                  checkpoint_error,
                  CASE
                      WHEN checkpoint_updated_at > 0 THEN checkpoint_updated_at
                      ELSE updated_at
                  END,
                  CASE
                      WHEN checkpoint_updated_at > 0 THEN checkpoint_updated_at
                      ELSE updated_at
                  END
           FROM cluster_jobs
           WHERE checkpoint_id <> ''"""
    )
    await connection.commit()


async def upsert_checkpoint(connection: aiosqlite.Connection, payload: dict) -> None:
    now = time.time()
    created_at = float(payload.get("created_at") or now)
    updated_at = float(payload.get("updated_at") or now)
    await connection.execute(
        """INSERT INTO cluster_checkpoints
           (checkpoint_id, job_id, allocation_id, node_id, runtime_job_handle,
            status, manifest_path, error, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(checkpoint_id) DO UPDATE SET
               job_id = excluded.job_id,
               allocation_id = excluded.allocation_id,
               node_id = excluded.node_id,
               runtime_job_handle = excluded.runtime_job_handle,
               status = excluded.status,
               manifest_path = excluded.manifest_path,
               error = excluded.error,
               updated_at = excluded.updated_at""",
        (
            str(payload["checkpoint_id"]),
            str(payload["job_id"]),
            str(payload.get("allocation_id") or ""),
            str(payload.get("node_id") or ""),
            str(payload.get("runtime_job_handle") or ""),
            str(payload.get("status") or ""),
            str(payload.get("manifest_path") or ""),
            str(payload.get("error") or ""),
            created_at,
            updated_at,
        ),
    )
    await connection.commit()


async def get_checkpoint(
    connection: aiosqlite.Connection,
    checkpoint_id: str,
) -> dict | None:
    cursor = await connection.execute(
        "SELECT * FROM cluster_checkpoints WHERE checkpoint_id = ?",
        (checkpoint_id,),
    )
    return _normalize_checkpoint(await cursor.fetchone())


async def list_checkpoints(
    connection: aiosqlite.Connection,
    *,
    job_id: str = "",
) -> list[dict]:
    query = """SELECT * FROM cluster_checkpoints"""
    params: tuple[str, ...] = ()
    if job_id:
        query += " WHERE job_id = ?"
        params = (job_id,)
    query += " ORDER BY updated_at DESC, checkpoint_id DESC"
    cursor = await connection.execute(query, params)
    rows = await cursor.fetchall()
    return [item for item in (_normalize_checkpoint(row) for row in rows) if item is not None]


async def get_latest_ready_checkpoint(
    connection: aiosqlite.Connection,
    job_id: str,
) -> dict | None:
    cursor = await connection.execute(
        """SELECT * FROM cluster_checkpoints
           WHERE job_id = ? AND status = 'checkpoint_ready'
           ORDER BY updated_at DESC, checkpoint_id DESC
           LIMIT 1""",
        (job_id,),
    )
    return _normalize_checkpoint(await cursor.fetchone())
