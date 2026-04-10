from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token


PUBLIC_WORKSPACE_KEY = "public"
USER_WORKSPACE_PREFIX = "user:"
ROLE_WORKSPACE_PREFIX = "role:"

_workspace_key_var: ContextVar[str] = ContextVar(
    "workspace_key",
    default=PUBLIC_WORKSPACE_KEY,
)


def build_workspace_key(user: dict | None, role: str | None = None) -> str:
    if user and user.get("id") is not None:
        return f"{USER_WORKSPACE_PREFIX}{int(user['id'])}"
    if role:
        return f"{ROLE_WORKSPACE_PREFIX}{role}"
    return PUBLIC_WORKSPACE_KEY


def current_workspace_key() -> str:
    return _workspace_key_var.get()


def set_workspace_key(key: str) -> Token:
    return _workspace_key_var.set(key or PUBLIC_WORKSPACE_KEY)


def reset_workspace_key(token: Token) -> None:
    _workspace_key_var.reset(token)


@contextmanager
def workspace_scope(key: str):
    token = set_workspace_key(key)
    try:
        yield key
    finally:
        reset_workspace_key(token)
