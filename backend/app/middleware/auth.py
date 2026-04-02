"""简单 Token 认证中间件 - 区分 observer / admin 角色

使用方式：
  - 请求头 Authorization: Bearer <token>
  - 管理员 token 由环境变量 ADMIN_TOKEN 配置（默认 "admin-token-change-me"）
  - 观察者 token 由环境变量 OBSERVER_TOKEN 配置（默认 "observer-token"）
  - 本机 localhost/127.0.0.1 首次使用时自动信任为 admin，避免桌面版和演示环境在没有 token UI 时卡住
  - 其他未携带 token 的请求仅可访问公开 API（/api/health、/ws、静态文件等）
"""

import os
import logging
from typing import Optional

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# 从环境变量读取令牌
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "admin-token-change-me")
OBSERVER_TOKEN = os.environ.get("OBSERVER_TOKEN", "observer-token")

# 公开路径前缀（无需认证）
PUBLIC_PREFIXES = (
    "/api/health",
    "/ws",
    "/docs",
    "/openapi.json",
    "/redoc",
)

TRUSTED_LOCAL_HOSTS = {
    "127.0.0.1",
    "::1",
    "0:0:0:0:0:0:0:1",
    "localhost",
}

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


def _is_local_request(request: Request) -> bool:
    """桌面版/本机浏览器访问默认视为受信本机请求。"""
    host = ((request.client.host if request.client else "") or "").strip().lower()
    return host in TRUSTED_LOCAL_HOSTS


class TokenAuthMiddleware(BaseHTTPMiddleware):
    """简单 Token 鉴权中间件"""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method.upper()

        # 公开路径放行
        if any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES):
            return await call_next(request)

        # 静态文件和非 API 路径放行
        if not path.startswith("/api"):
            return await call_next(request)

        # 解析角色
        token = _extract_token(request)
        role = _resolve_role(token)

        # 本机首次使用时，允许直接完成接入与治理操作
        if role is None and _is_local_request(request):
            request.state.role = "admin"
            return await call_next(request)

        # 未认证
        if role is None:
            # GET 请求宽松策略：允许无 token 访问只读 API（便于前端开发调试）
            # 生产环境可改为严格拒绝
            if method == "GET":
                request.state.role = "anonymous"
                return await call_next(request)
            return JSONResponse(
                status_code=401,
                content={"detail": "未提供有效的认证令牌", "code": "UNAUTHORIZED"},
            )

        # 管理员操作鉴权
        if method in ("POST", "PUT", "DELETE", "PATCH"):
            is_admin_path = any(path.startswith(prefix) for prefix in ADMIN_ONLY_PREFIXES)
            if is_admin_path and role != "admin":
                return JSONResponse(
                    status_code=403,
                    content={"detail": "此操作需要管理员权限", "code": "FORBIDDEN"},
                )

        request.state.role = role
        return await call_next(request)
