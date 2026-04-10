"""平台会话优先的认证中间件，保留静态 token 兼容通道。

使用方式：
  - 优先解析平台 session：Authorization: Bearer <session-token>
  - 兼容旧静态 token：ADMIN_TOKEN / OBSERVER_TOKEN
  - 首次强制改密用户只能访问改密相关接口
"""

import os
import logging
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.services.workspace_context import (
    build_workspace_key,
    reset_workspace_key,
    set_workspace_key,
)

logger = logging.getLogger(__name__)

# 从环境变量读取令牌
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "admin-token-change-me")
OBSERVER_TOKEN = os.environ.get("OBSERVER_TOKEN", "observer-token")

SESSION_PUBLIC_PREFIXES = (
    "/api/health",
    "/api/auth/login",
    "/docs",
    "/openapi.json",
    "/redoc",
)

PASSWORD_CHANGE_ALLOWED_PREFIXES = (
    "/api/auth/me",
    "/api/auth/logout",
    "/api/auth/change-password",
    "/api/health",
)

# 仅管理员可执行的危险路径（POST/PUT/DELETE 操作）
ADMIN_ONLY_PREFIXES = (
    "/api/tasks/pause",
    "/api/tasks/resume",
    "/api/tasks/terminate",
    "/api/scheduler/auto",
    "/api/scheduler/budget",
    "/api/scheduler/carbon-budget",
    "/api/scheduler/power-limit",
    "/api/scheduler/run-once",
    "/api/agent-runtime",
    "/api/governance/rules",
    "/api/system/connection",
    "/api/system/import-context",
    "/api/system/llm",
)


def _extract_token(request: Request) -> Optional[str]:
    """从 Authorization 头提取 Bearer token"""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    # 兼容：也可通过 query param 传递
    return request.query_params.get("token")


def _resolve_role(token: Optional[str]) -> Optional[str]:
    """根据 token 解析角色"""
    if not token:
        return None
    if token == ADMIN_TOKEN:
        return "admin"
    if token == OBSERVER_TOKEN:
        return "observer"
    return None

class TokenAuthMiddleware(BaseHTTPMiddleware):
    """平台会话优先的鉴权中间件"""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method.upper()
        token = _extract_token(request)
        session_user = await self._resolve_session_user(token)
        role = self._apply_identity(request, token, session_user)
        workspace_key = build_workspace_key(session_user, role)
        await self._ensure_workspace(workspace_key)
        workspace_token = set_workspace_key(workspace_key)

        try:
            if any(path.startswith(prefix) for prefix in SESSION_PUBLIC_PREFIXES):
                return await call_next(request)
            if not path.startswith("/api"):
                return await call_next(request)
            if session_user is not None:
                return await self._handle_session_user(request, call_next, path)
            if role is None:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "请先登录平台", "code": "UNAUTHORIZED"},
                )
            if method in ("POST", "PUT", "DELETE", "PATCH"):
                is_admin_path = any(path.startswith(prefix) for prefix in ADMIN_ONLY_PREFIXES)
                if is_admin_path and role != "admin":
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "此操作需要管理员权限", "code": "FORBIDDEN"},
                    )
            return await call_next(request)
        finally:
            reset_workspace_key(workspace_token)

    async def _resolve_session_user(self, token: Optional[str]) -> Optional[dict]:
        if not token:
            return None
        from app.main import app_state

        return await app_state.platform_auth.resolve_session(token)

    def _apply_identity(
        self,
        request: Request,
        token: Optional[str],
        session_user: Optional[dict],
    ) -> Optional[str]:
        if session_user is not None:
            request.state.user = session_user
            request.state.role = session_user["role"]
            request.state.auth_token = token
            return session_user["role"]
        role = _resolve_role(token)
        if role is not None:
            request.state.role = role
            request.state.auth_token = token
        return role

    async def _handle_session_user(self, request: Request, call_next, path: str):
        user = request.state.user
        if not user["must_change_password"]:
            return await call_next(request)
        allowed = any(path.startswith(prefix) for prefix in PASSWORD_CHANGE_ALLOWED_PREFIXES)
        if allowed:
            return await call_next(request)
        return JSONResponse(
            status_code=403,
            content={"detail": "首次登录后必须先修改密码", "code": "PASSWORD_CHANGE_REQUIRED"},
        )

    async def _ensure_workspace(self, workspace_key: str) -> None:
        from app.main import app_state

        workspaces = getattr(app_state, "workspaces", None)
        if workspaces is not None:
            await workspaces.ensure_workspace(workspace_key)
