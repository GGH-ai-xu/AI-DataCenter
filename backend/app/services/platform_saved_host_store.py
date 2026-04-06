from __future__ import annotations

import time
from collections.abc import Callable

import aiosqlite


SAVED_HOSTS_INIT_SQL = """
CREATE TABLE IF NOT EXISTS saved_hosts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_user_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    provider_type TEXT NOT NULL,
    host TEXT,
    port INTEGER,
    username TEXT,
    auth_type TEXT,
    sudo_enabled INTEGER NOT NULL DEFAULT 0,
    host_fingerprint TEXT,
    agent_url TEXT,
    credential_ref TEXT,
    last_connected_at REAL NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    FOREIGN KEY (owner_user_id) REFERENCES platform_users(id)
);
"""


class PlatformSavedHostStore:
    def __init__(
        self,
        db: aiosqlite.Connection,
        clock: Callable[[], float] = time.time,
    ):
        self.db = db
        self.clock = clock

    async def upsert_saved_host(
        self,
        owner_user_id: int,
        label: str,
        provider_type: str,
        host: str | None,
        port: int | None,
        username: str | None,
        auth_type: str | None,
        sudo_enabled: bool,
        host_fingerprint: str | None,
        agent_url: str | None,
        credential_ref: str | None,
    ) -> dict:
        existing_id = await self._find_saved_host_id(
            owner_user_id,
            provider_type,
            host,
            port,
            username,
            agent_url,
        )
        if existing_id is None:
            return await self._insert_saved_host(
                owner_user_id,
                label,
                provider_type,
                host,
                port,
                username,
                auth_type,
                sudo_enabled,
                host_fingerprint,
                agent_url,
                credential_ref,
            )
        await self._update_saved_host(
            existing_id,
            label,
            auth_type,
            sudo_enabled,
            host_fingerprint,
            credential_ref,
        )
        return await self.get_saved_host(existing_id)

    async def list_saved_hosts(self, owner_user_id: int | None = None) -> list[dict]:
        sql = """SELECT h.*, u.username AS owner_username
                 FROM saved_hosts h
                 JOIN platform_users u ON u.id = h.owner_user_id"""
        params: tuple[int, ...] = ()
        if owner_user_id is not None:
            sql += " WHERE h.owner_user_id = ?"
            params = (owner_user_id,)
        sql += " ORDER BY h.updated_at DESC"
        rows = await (await self.db.execute(sql, params)).fetchall()
        return [_row_to_dict(row) for row in rows]

    async def get_saved_host(self, host_id: int) -> dict | None:
        row = await (await self.db.execute(
            """SELECT h.*, u.username AS owner_username
               FROM saved_hosts h
               JOIN platform_users u ON u.id = h.owner_user_id
               WHERE h.id = ?""",
            (host_id,),
        )).fetchone()
        return _row_to_dict(row)

    async def delete_saved_host(self, host_id: int) -> None:
        await self.db.execute("DELETE FROM saved_hosts WHERE id = ?", (host_id,))
        await self.db.commit()

    async def _find_saved_host_id(
        self,
        owner_user_id: int,
        provider_type: str,
        host: str | None,
        port: int | None,
        username: str | None,
        agent_url: str | None,
    ) -> int | None:
        row = await (await self.db.execute(
            """SELECT id FROM saved_hosts
               WHERE owner_user_id = ? AND provider_type = ?
                 AND COALESCE(host, '') = COALESCE(?, '')
                 AND COALESCE(port, 0) = COALESCE(?, 0)
                 AND COALESCE(username, '') = COALESCE(?, '')
                 AND COALESCE(agent_url, '') = COALESCE(?, '')""",
            (owner_user_id, provider_type, host, port, username, agent_url),
        )).fetchone()
        if not row:
            return None
        return int(row["id"])

    async def _update_saved_host(
        self,
        host_id: int,
        label: str,
        auth_type: str | None,
        sudo_enabled: bool,
        host_fingerprint: str | None,
        credential_ref: str | None,
    ) -> None:
        now = self.clock()
        await self.db.execute(
            """UPDATE saved_hosts
               SET label = ?, auth_type = ?, sudo_enabled = ?, host_fingerprint = ?,
                   credential_ref = ?, last_connected_at = ?, updated_at = ?
               WHERE id = ?""",
            (
                label,
                auth_type,
                int(sudo_enabled),
                host_fingerprint,
                credential_ref,
                now,
                now,
                host_id,
            ),
        )
        await self.db.commit()

    async def _insert_saved_host(
        self,
        owner_user_id: int,
        label: str,
        provider_type: str,
        host: str | None,
        port: int | None,
        username: str | None,
        auth_type: str | None,
        sudo_enabled: bool,
        host_fingerprint: str | None,
        agent_url: str | None,
        credential_ref: str | None,
    ) -> dict:
        now = self.clock()
        cursor = await self.db.execute(
            """INSERT INTO saved_hosts
               (owner_user_id, label, provider_type, host, port, username, auth_type, sudo_enabled,
                host_fingerprint, agent_url, credential_ref, last_connected_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                owner_user_id,
                label,
                provider_type,
                host,
                port,
                username,
                auth_type,
                int(sudo_enabled),
                host_fingerprint,
                agent_url,
                credential_ref,
                now,
                now,
                now,
            ),
        )
        await self.db.commit()
        return await self.get_saved_host(cursor.lastrowid)


def _row_to_dict(row) -> dict | None:
    return dict(row) if row else None
