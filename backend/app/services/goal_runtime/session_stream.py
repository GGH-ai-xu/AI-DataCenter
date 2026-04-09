from __future__ import annotations

import asyncio
from collections import defaultdict


class GoalRuntimeSessionStreamBroker:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

    async def publish(self, session_id: str, event: str, data: dict) -> None:
        for queue in list(self._subscribers.get(session_id, [])):
            await queue.put({"event": event, "data": data})

    async def subscribe(self, session_id: str):
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[session_id].append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            subscribers = self._subscribers.get(session_id, [])
            if queue in subscribers:
                subscribers.remove(queue)
            if not subscribers and session_id in self._subscribers:
                del self._subscribers[session_id]
