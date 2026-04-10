"""WebSocket实时推送 - 按 workspace 隔离广播实时数据。"""

import asyncio
import json
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 连接管理器。"""

    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, ws: WebSocket, workspace_key: str):
        await ws.accept()
        sockets = self._connections.setdefault(workspace_key, set())
        sockets.add(ws)
        logger.info("WebSocket连接建立，workspace=%s 当前连接数=%s", workspace_key, len(sockets))

    def disconnect(self, ws: WebSocket, workspace_key: str | None = None):
        if workspace_key is not None:
            self._discard(workspace_key, ws)
            return
        for key in list(self._connections):
            self._discard(key, ws)

    def _discard(self, workspace_key: str, ws: WebSocket) -> None:
        sockets = self._connections.get(workspace_key)
        if not sockets:
            return
        sockets.discard(ws)
        if sockets:
            logger.info("WebSocket连接断开，workspace=%s 当前连接数=%s", workspace_key, len(sockets))
            return
        self._connections.pop(workspace_key, None)
        logger.info("WebSocket连接断开，workspace=%s 当前连接数=0", workspace_key)

    async def broadcast(self, workspace_key: str, data: dict):
        sockets = list(self._connections.get(workspace_key) or ())
        if not sockets:
            return
        message = json.dumps(data, ensure_ascii=False)
        results = await asyncio.gather(
            *(ws.send_text(message) for ws in sockets),
            return_exceptions=True,
        )
        dead = {
            ws
            for ws, result in zip(sockets, results)
            if isinstance(result, Exception)
        }
        for ws in dead:
            self._discard(workspace_key, ws)

    def connection_count_for(self, workspace_key: str) -> int:
        return len(self._connections.get(workspace_key) or ())

    @property
    def connection_count(self) -> int:
        return sum(len(sockets) for sockets in self._connections.values())


ws_manager = ConnectionManager()
