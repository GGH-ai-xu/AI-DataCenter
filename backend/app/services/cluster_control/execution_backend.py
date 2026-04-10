from __future__ import annotations

import httpx


class HTTPAgentProcessBackend:
    def __init__(self, client_factory=httpx.AsyncClient, timeout_seconds: float = 10.0):
        self._client_factory = client_factory
        self._timeout_seconds = timeout_seconds

    async def create_reservation(self, node: dict, payload: dict) -> dict:
        return await self._post(node, "/api/runtime/reservations", payload)

    async def launch_job(self, node: dict, payload: dict) -> dict:
        return await self._post(node, "/api/runtime/jobs/launch", payload)

    async def _post(self, node: dict, path: str, payload: dict) -> dict:
        base_url = str(node["base_url"]).rstrip("/")
        async with self._client_factory(
            base_url=base_url,
            timeout=self._timeout_seconds,
        ) as client:
            response = await client.post(path, json=payload)
        response.raise_for_status()
        return response.json()


class SSHProcessBackend:
    async def create_reservation(self, node: dict, payload: dict) -> dict:
        raise NotImplementedError("ssh node runtime backend is not implemented yet")

    async def launch_job(self, node: dict, payload: dict) -> dict:
        raise NotImplementedError("ssh node runtime backend is not implemented yet")


class LocalProcessBackend:
    async def create_reservation(self, node: dict, payload: dict) -> dict:
        raise NotImplementedError("local node runtime backend is not implemented yet")

    async def launch_job(self, node: dict, payload: dict) -> dict:
        raise NotImplementedError("local node runtime backend is not implemented yet")
