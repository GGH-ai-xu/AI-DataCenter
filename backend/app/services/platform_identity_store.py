from __future__ import annotations

import hashlib
import os
import time
from typing import Optional

import aiosqlite

from app.services.platform_saved_host_store import (
    PlatformSavedHostStore,
    SAVED_HOSTS_INIT_SQL,
)


SQLITE_TIMEOUT_SECONDS = 30.0
ACTIVE_FLAG = 1

_INIT_SQL = (
    """
CREATE TABLE IF NOT EXISTS platform_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    must_change_password INTEGER NOT NULL DEFAULT 1,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    last_login_at REAL
);

CREATE TABLE IF NOT EXISTS platform_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_token_hash TEXT NOT NULL UNIQUE,
    expires_at REAL NOT NULL,
    created_at REAL NOT NULL,
    last_seen_at REAL NOT NULL,
    revoked_at REAL,
    FOREIGN KEY (user_id) REFERENCES platform_users(id)
);
"""
    + SAVED_HOSTS_INIT_SQL
)


class PlatformIdentityStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None
        self._saved_hosts: PlatformSavedHostStore | None = None

    async def init(self):
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._db = await aiosqlite.connect(
            self.db_path,
            timeout=SQLITE_TIMEOUT_SECONDS,
        )
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_INIT_SQL)
        await self._db.commit()
        self._saved_hosts = PlatformSavedHostStore(self._db)

    async def close(self):
        if self._db:
            await self._db.close()

    async def get_user_by_username(self, username: str) -> dict | None:
        db = self._require_db()
        row = await (await db.execute(
            "SELECT * FROM platform_users WHERE username = ?",
            (username,),
        )).fetchone()
        return _row_to_dict(row)

    async def get_user_by_id(self, user_id: int) -> dict | None:
        db = self._require_db()
        row = await (await db.execute(
            "SELECT * FROM platform_users WHERE id = ?",
            (user_id,),
        )).fetchone()
        return _row_to_dict(row)

    async def create_user(
        self,
        username: str,
        password_hash: str,
        role: str,
        must_change_password: bool,
    ) -> dict:
        db = self._require_db()
        now = time.time()
        cursor = await db.execute(
            """INSERT INTO platform_users
               (username, password_hash, role, must_change_password, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                username,
                password_hash,
                role,
                int(must_change_password),
                ACTIVE_FLAG,
                now,
                now,
            ),
        )
        await db.commit()
        return await self.get_user_by_id(cursor.lastrowid)

    async def update_password(
        self,
        user_id: int,
        password_hash: str,
        must_change_password: bool,
    ) -> None:
        db = self._require_db()
        await db.execute(
            """UPDATE platform_users
               SET password_hash = ?, must_change_password = ?, updated_at = ?
               WHERE id = ?""",
            (password_hash, int(must_change_password), time.time(), user_id),
        )
        await db.commit()

    async def create_session(
        self,
        user_id: int,
        token_hash: str,
        expires_at: float,
    ) -> None:
        db = self._require_db()
        now = time.time()
        await db.execute(
            """INSERT INTO platform_sessions
               (user_id, session_token_hash, expires_at, created_at, last_seen_at)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, token_hash, expires_at, now, now),
        )
        await db.execute(
            "UPDATE platform_users SET last_login_at = ? WHERE id = ?",
            (now, user_id),
        )
        await db.commit()

    async def get_session_by_token(self, raw_token: str) -> dict | None:
        db = self._require_db()
        row = await (await db.execute(
            """SELECT s.*, u.username, u.role, u.must_change_password, u.is_active
               FROM platform_sessions s
               JOIN platform_users u ON u.id = s.user_id
               WHERE s.session_token_hash = ? AND s.revoked_at IS NULL""",
            (_hash_token(raw_token),),
        )).fetchone()
        return _row_to_dict(row)

    async def revoke_session(self, raw_token: str) -> None:
        db = self._require_db()
        await db.execute(
            """UPDATE platform_sessions
               SET revoked_at = ?
               WHERE session_token_hash = ? AND revoked_at IS NULL""",
            (time.time(), _hash_token(raw_token)),
        )
        await db.commit()

    async def list_users(self) -> list[dict]:
        db = self._require_db()
        rows = await (await db.execute(
            """SELECT id, username, role, must_change_password, is_active, created_at, updated_at, last_login_at
               FROM platform_users
               ORDER BY username ASC"""
        )).fetchall()
        return [_row_to_dict(row) for row in rows]

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
        return await self._saved_host_store().upsert_saved_host(
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

    async def list_saved_hosts(self, owner_user_id: int | None = None) -> list[dict]:
        return await self._saved_host_store().list_saved_hosts(owner_user_id)

    async def get_saved_host(self, host_id: int) -> dict | None:
        return await self._saved_host_store().get_saved_host(host_id)

    async def delete_saved_host(self, host_id: int) -> None:
        await self._saved_host_store().delete_saved_host(host_id)

    def _require_db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("platform identity store 尚未初始化")
        return self._db

    def _saved_host_store(self) -> PlatformSavedHostStore:
        if self._saved_hosts is None:
            raise RuntimeError("saved host store 尚未初始化")
        return self._saved_hosts


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(str(raw_token).encode("utf-8")).hexdigest()


def _row_to_dict(row) -> dict | None:
    return dict(row) if row else None
