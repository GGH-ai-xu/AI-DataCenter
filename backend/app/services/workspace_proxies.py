from __future__ import annotations


class WorkspaceImportContextProxy:
    def __init__(self, workspaces):
        self._workspaces = workspaces

    def __getattr__(self, name: str):
        return getattr(self._workspaces.current().import_context, name)


class WorkspaceRuntimeProxy:
    def __init__(self, workspaces):
        self._workspaces = workspaces

    def __getattr__(self, name: str):
        return getattr(self._workspaces.current().runtime, name)


class WorkspaceAgentProxy:
    def __init__(self, workspaces):
        self._workspaces = workspaces

    def __getattr__(self, name: str):
        async def call(*args, **kwargs):
            provider = await self._workspaces.current_provider()
            method = getattr(provider, name)
            return await method(*args, **kwargs)

        return call
