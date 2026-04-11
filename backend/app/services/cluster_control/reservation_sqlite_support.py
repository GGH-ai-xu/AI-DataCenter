from __future__ import annotations

import json
import time

import aiosqlite


def _loads_json(value: str) -> list[str]:
    if not value:
        return []
    return list(json.loads(value))


def _dumps_json(value: list[str] | tuple[str, ...]) -> str:
    return json.dumps(list(value), ensure_ascii=False, sort_keys=True)


def _normalize_reservation(row: aiosqlite.Row | None) -> dict | None:
    if row is None:
        return None
    item = dict(row)
    item["device_ids"] = _loads_json(item.pop("device_ids_json"))
    return item


async def create_reservation(connection: aiosqlite.Connection, payload: dict) -> None:
    now = time.time()
    await connection.execute(
        """INSERT INTO cluster_reservations
           (reservation_id, job_id, node_id, device_ids_json, status, created_at, expires_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            payload["reservation_id"],
            payload["job_id"],
            payload["node_id"],
            _dumps_json(payload.get("device_ids", [])),
            str(payload.get("status") or "reserved"),
            now,
            float(payload.get("expires_at") or now + 60.0),
        ),
    )
    await connection.commit()


async def get_reservation(
    connection: aiosqlite.Connection,
    reservation_id: str,
) -> dict | None:
    cursor = await connection.execute(
        "SELECT * FROM cluster_reservations WHERE reservation_id = ?",
        (reservation_id,),
    )
    return _normalize_reservation(await cursor.fetchone())


async def list_reservations(
    connection: aiosqlite.Connection,
    *,
    job_id: str = "",
) -> list[dict]:
    if job_id:
        cursor = await connection.execute(
            """SELECT * FROM cluster_reservations
               WHERE job_id = ?
               ORDER BY created_at DESC, reservation_id DESC""",
            (job_id,),
        )
    else:
        cursor = await connection.execute(
            """SELECT * FROM cluster_reservations
               ORDER BY created_at DESC, reservation_id DESC"""
        )
    rows = await cursor.fetchall()
    return [_normalize_reservation(row) for row in rows if row is not None]


async def update_reservation_status(
    connection: aiosqlite.Connection,
    reservation_id: str,
    status: str,
) -> None:
    await connection.execute(
        """UPDATE cluster_reservations
           SET status = ?
           WHERE reservation_id = ?""",
        (status, reservation_id),
    )
    await connection.commit()
