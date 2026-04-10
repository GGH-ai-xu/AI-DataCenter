from __future__ import annotations

import asyncio
import copy
import os
import re
from dataclasses import dataclass, field

from app.services.import_context import ImportContextService
from app.services.runtime_provider_manager import RuntimeProviderManager
from app.services.runtime_snapshot import empty_runtime_snapshot
from app.services.workspace_context import PUBLIC_WORKSPACE_KEY, current_workspace_key


REMOTE_MODE = "remote"
LOCAL_MODE = "local"
HTTP_LOCAL_PROVIDER = "http_local"
HTTP_REMOTE_PROVIDER = "http_remote"
SSH_LINUX_PROVIDER = "ssh_linux"
SSH_DEFAULT_PORT = 22
WORKSPACE_DIRNAME = "workspaces"
IMPORT_CONTEXT_FILENAME = "import-context.json"
PATH_SAFE_PATTERN = re.compile(r"[^a-zA-Z0-9._-]+")


@dataclass
class UserWorkspace:
    key: str
    import_context: ImportContextService
    runtime: RuntimeProviderManager
    latest_runtime_snapshot: dict = field(default_factory=empty_runtime_snapshot)


def _workspace_path_component(key: str) -> str:
    normalized = PATH_SAFE_PATTERN.sub("-", key.strip() or PUBLIC_WORKSPACE_KEY)
    return normalized.strip("-") or PUBLIC_WORKSPACE_KEY


def _provider_target_url(target: dict | None, default_local_url: str) -> str:
    if not target:
        return default_local_url
    if target.get("agent_url"):
        return str(target["agent_url"])
    username = target.get("username") or "unknown"
    host = target.get("host") or "unknown"
    port = int(target.get("port") or SSH_DEFAULT_PORT)
    return f"ssh://{username}@{host}:{port}"


def _provider_mode(target: dict | None) -> str:
    provider_type = str((target or {}).get("provider_type") or HTTP_LOCAL_PROVIDER)
    return LOCAL_MODE if provider_type == HTTP_LOCAL_PROVIDER else REMOTE_MODE


def _provider_mode_label(target: dict | None) -> str:
    provider_type = str((target or {}).get("provider_type") or HTTP_LOCAL_PROVIDER)
    if provider_type == SSH_LINUX_PROVIDER:
        return "SSH Linux"
    if provider_type == HTTP_REMOTE_PROVIDER:
        return "远程服务器模式"
    return "本机模式"


def _provider_hint(target: dict | None) -> str:
    provider_type = str((target or {}).get("provider_type") or HTTP_LOCAL_PROVIDER)
    if provider_type == SSH_LINUX_PROVIDER:
        return "通过 SSH 连接目标 Linux 主机采集与执行"
    if provider_type == HTTP_REMOTE_PROVIDER:
        return "连接指定服务器上的 Agent 采集与执行"
    return "使用当前电脑上的 Agent 采集与执行"


class UserWorkspaceService:
    def __init__(
        self,
        *,
        runtime_root: str,
        default_local_url: str,
        default_target_reader,
        default_secret_reader,
        provider_factory,
    ):
        self._runtime_root = runtime_root
        self._default_local_url = default_local_url
        self._default_target_reader = default_target_reader
        self._default_secret_reader = default_secret_reader
        self._provider_factory = provider_factory
        self._workspaces: dict[str, UserWorkspace] = {}
        self._lock = asyncio.Lock()

    def _build_workspace(self, key: str) -> UserWorkspace:
        workspace_dir = os.path.join(
            self._runtime_root,
            WORKSPACE_DIRNAME,
            _workspace_path_component(key),
        )
        import_context = ImportContextService(
            os.path.join(workspace_dir, IMPORT_CONTEXT_FILENAME),
            self._default_local_url,
        )
        import_context.load()
        return UserWorkspace(
            key=key,
            import_context=import_context,
            runtime=RuntimeProviderManager(self._provider_factory),
        )

    async def _bootstrap_workspace(self, workspace: UserWorkspace) -> None:
        target = self._default_target_reader()
        secret = dict(self._default_secret_reader(target) or {})
        await workspace.runtime.switch(target, secret)

    async def ensure_workspace(self, key: str | None) -> UserWorkspace:
        resolved_key = key or PUBLIC_WORKSPACE_KEY
        existing = self._workspaces.get(resolved_key)
        if existing is not None:
            return existing
        async with self._lock:
            existing = self._workspaces.get(resolved_key)
            if existing is not None:
                return existing
            workspace = self._build_workspace(resolved_key)
            try:
                await self._bootstrap_workspace(workspace)
            except Exception:
                self._workspaces.pop(resolved_key, None)
                raise
            self._workspaces[resolved_key] = workspace
            return workspace

    def require_workspace(self, key: str | None = None) -> UserWorkspace:
        resolved_key = key or current_workspace_key()
        workspace = self._workspaces.get(resolved_key)
        if workspace is None:
            raise RuntimeError(f"workspace is not initialized: {resolved_key}")
        return workspace

    def current(self) -> UserWorkspace:
        return self.require_workspace()

    async def current_provider(self):
        return await self.current().runtime.current_provider()

    def current_snapshot(self) -> dict:
        return copy.deepcopy(self.current().latest_runtime_snapshot)

    def set_current_snapshot(self, snapshot: dict) -> None:
        self.current().latest_runtime_snapshot = copy.deepcopy(snapshot)

    def current_connection_snapshot(self, agent_health: dict | None) -> dict:
        workspace = self.current()
        target = workspace.runtime.target_snapshot()
        connected = bool(agent_health and agent_health.get("status") == "ok")
        return {
            "mode": _provider_mode(target),
            "mode_label": _provider_mode_label(target),
            "agent_url": _provider_target_url(target, self._default_local_url),
            "agent_label": (target or {}).get("label") or "本机 Agent",
            "connected": connected,
            "updated_at": workspace.import_context.snapshot().get("imported_at"),
            "default_local_url": self._default_local_url,
            "target_hint": _provider_hint(target),
            "agent_health": agent_health,
        }

    def all_workspaces(self) -> list[UserWorkspace]:
        return list(self._workspaces.values())

    async def close_all(self) -> None:
        workspaces = list(self._workspaces.values())
        self._workspaces.clear()
        await asyncio.gather(
            *(workspace.runtime.close() for workspace in workspaces),
            return_exceptions=True,
        )
