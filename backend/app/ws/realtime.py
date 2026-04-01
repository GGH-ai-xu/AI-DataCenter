"""WebSocket实时推送 - 向前端推送GPU实时数据和告警"""

import asyncio
import json
import logging
from typing import Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket连接管理器"""

    def __init__(self):
        self._connections: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.add(ws)
        logger.info(f"WebSocket连接建立，当前连接数: {len(self._connections)}")

    def disconnect(self, ws: WebSocket):
        self._connections.discard(ws)
        logger.info(f"WebSocket连接断开，当前连接数: {len(self._connections)}")

    async def broadcast(self, data: dict):
        """广播数据到所有连接的客户端"""
        if not self._connections:
            return
        message = json.dumps(data, ensure_ascii=False)
        sockets = list(self._connections)
        results = await asyncio.gather(
            *(ws.send_text(message) for ws in sockets),
            return_exceptions=True,
        )
        dead = {
            ws
            for ws, result in zip(sockets, results)
            if isinstance(result, Exception)
        }
        # 清理断开的连接
        self._connections -= dead

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# 全局连接管理器
ws_manager = ConnectionManager()
