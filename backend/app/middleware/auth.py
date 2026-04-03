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
    "/api/ai/control/execute",
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

        # 公开路径放行
        if any(path.startswith(prefix) for prefix in SESSION_PUBLIC_PREFIXES):
            return await call_next(request)

        # 静态文件和非 API 路径放行
        if not path.startswith("/api"):
            return await call_next(request)

        token = _extract_token(request)
        session_user = None
        if token:
            try:
                from app.main import app_state
                session_user = await app_state.platform_auth.resolve_session(token)
            except Exception as exc:
                logger.debug("session resolve failed: %s", exc)

        if session_user is not None:
            request.state.user = session_user
            request.state.role = session_user["role"]
            request.state.auth_token = token
            if session_user["must_change_password"]:
                allowed = any(path.startswith(prefix) for prefix in PASSWORD_CHANGE_ALLOWED_PREFIXES)
                if not allowed:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "首次登录后必须先修改密码", "code": "PASSWORD_CHANGE_REQUIRED"},
                    )
            return await call_next(request)

        role = _resolve_role(token)
        if role is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "请先登录平台", "code": "UNAUTHORIZED"},
            )

        request.state.role = role
        if method in ("POST", "PUT", "DELETE", "PATCH"):
            is_admin_path = any(path.startswith(prefix) for prefix in ADMIN_ONLY_PREFIXES)
            if is_admin_path and role != "admin":
                return JSONResponse(
                    status_code=403,
                    content={"detail": "此操作需要管理员权限", "code": "FORBIDDEN"},
                )

        return await call_next(request)
