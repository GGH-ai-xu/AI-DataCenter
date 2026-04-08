from __future__ import annotations

import hashlib
import os
import secrets
import time

from app.services.password_hasher import hash_password, verify_password


DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_ROLE = "admin"
DEFAULT_ADMIN_PASSWORD = os.environ.get("GPU_GOV_DEFAULT_ADMIN_PASSWORD", "admin123456")
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60
TOKEN_BYTES = 32


class PlatformAuthService:
    def __init__(self, store):
        self.store = store

    async def ensure_default_admin(self) -> dict | None:
        current = await self.store.get_user_by_username(DEFAULT_ADMIN_USERNAME)
        if current:
            if _can_reset_bootstrap_admin(current):
                await self.store.update_password(
                    current["id"],
                    hash_password(DEFAULT_ADMIN_PASSWORD),
                    False,
                )
                refreshed = await self.store.get_user_by_id(current["id"])
                return {
                    "username": refreshed["username"],
                    "default_password": DEFAULT_ADMIN_PASSWORD,
                    "status": "reset_existing",
                }
            return None
        user = await self.store.create_user(
            username=DEFAULT_ADMIN_USERNAME,
            password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
            role=DEFAULT_ADMIN_ROLE,
            must_change_password=False,
        )
        return {
            "username": user["username"],
            "default_password": DEFAULT_ADMIN_PASSWORD,
            "status": "created",
        }

    async def login(self, username: str, password: str) -> dict:
        user = await self.store.get_user_by_username(username)
        if not user or not user.get("is_active"):
            raise ValueError("用户名或密码错误")
        if not verify_password(password, user["password_hash"]):
            raise ValueError("用户名或密码错误")
        token = secrets.token_urlsafe(TOKEN_BYTES)
        await self.store.create_session(
            user_id=user["id"],
            token_hash=_hash_token(token),
            expires_at=time.time() + SESSION_TTL_SECONDS,
        )
        fresh_user = await self.store.get_user_by_id(user["id"])
        return {"token": token, "user": _public_user(fresh_user)}

    async def resolve_session(self, token: str) -> dict | None:
        if not token:
            return None
        session = await self.store.get_session_by_token(token)
        if not session:
            return None
        if session.get("revoked_at") is not None:
            return None
        if float(session.get("expires_at") or 0) <= time.time():
            return None
        if not session.get("is_active"):
            return None
        return {
            "id": session["user_id"],
            "username": session["username"],
            "role": session["role"],
            "must_change_password": bool(session["must_change_password"]),
        }

    async def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str,
    ) -> None:
        user = await self.store.get_user_by_id(user_id)
        if not user or not verify_password(current_password, user["password_hash"]):
            raise ValueError("当前密码错误")
        await self.store.update_password(user_id, hash_password(new_password), False)

    async def logout(self, token: str) -> None:
        await self.store.revoke_session(token)

    async def create_user(
        self,
        username: str,
        password: str,
        role: str,
        must_change_password: bool,
    ) -> dict:
        existing = await self.store.get_user_by_username(username)
        if existing:
            raise ValueError("用户名已存在")
        user = await self.store.create_user(
            username=username,
            password_hash=hash_password(password),
            role=role,
            must_change_password=must_change_password,
        )
        return _public_user(user)

    async def reset_password(
        self,
        user_id: int,
        password: str,
        must_change_password: bool,
    ) -> None:
        user = await self.store.get_user_by_id(user_id)
        if not user:
            raise ValueError("用户不存在")
        await self.store.update_password(
            user_id,
            hash_password(password),
            must_change_password,
        )


def _hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _can_reset_bootstrap_admin(user: dict) -> bool:
    return bool(user.get("must_change_password")) and user.get("last_login_at") is None


def _public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "must_change_password": bool(user["must_change_password"]),
    }
