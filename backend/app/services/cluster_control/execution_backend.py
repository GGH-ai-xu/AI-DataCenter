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

    async def list_jobs(self, node: dict) -> list[dict]:
        payload = await self._get(node, "/api/runtime/jobs")
        return list(payload.get("jobs") or [])

    async def get_job(self, node: dict, job_handle: str) -> dict:
        return await self._get(node, f"/api/runtime/jobs/{job_handle}")

    async def pause_job(self, node: dict, job_handle: str) -> dict:
        return await self._post(node, f"/api/runtime/jobs/{job_handle}/pause", {})

    async def resume_job(self, node: dict, job_handle: str) -> dict:
        return await self._post(node, f"/api/runtime/jobs/{job_handle}/resume", {})

    async def checkpoint_job(self, node: dict, job_handle: str, payload: dict) -> dict:
        return await self._post(node, f"/api/runtime/jobs/{job_handle}/checkpoint", payload)

    async def get_checkpoint(self, node: dict, job_handle: str) -> dict:
        return await self._get(node, f"/api/runtime/jobs/{job_handle}/checkpoint")

    async def restore_job(self, node: dict, payload: dict) -> dict:
        job_handle = str(payload["job_handle"])
        return await self._post(node, f"/api/runtime/jobs/{job_handle}/restore", payload)

    async def terminate_job(self, node: dict, job_handle: str) -> dict:
        return await self._post(node, f"/api/runtime/jobs/{job_handle}/terminate", {})

    async def _post(self, node: dict, path: str, payload: dict) -> dict:
        base_url = str(node["base_url"]).rstrip("/")
        async with self._client_factory(
            base_url=base_url,
            timeout=self._timeout_seconds,
        ) as client:
            response = await client.post(path, json=payload)
        response.raise_for_status()
        return response.json()

    async def _get(self, node: dict, path: str) -> dict:
        base_url = str(node["base_url"]).rstrip("/")
        async with self._client_factory(
            base_url=base_url,
            timeout=self._timeout_seconds,
        ) as client:
            response = await client.get(path)
        response.raise_for_status()
        return response.json()


class SSHProcessBackend:
    async def create_reservation(self, node: dict, payload: dict) -> dict:
        raise NotImplementedError("ssh node runtime backend is not implemented yet")

    async def launch_job(self, node: dict, payload: dict) -> dict:
        raise NotImplementedError("ssh node runtime backend is not implemented yet")

    async def list_jobs(self, node: dict) -> list[dict]:
        raise NotImplementedError("ssh node runtime backend is not implemented yet")

    async def get_job(self, node: dict, job_handle: str) -> dict:
        raise NotImplementedError("ssh node runtime backend is not implemented yet")

    async def pause_job(self, node: dict, job_handle: str) -> dict:
        raise NotImplementedError("ssh node runtime backend is not implemented yet")

    async def resume_job(self, node: dict, job_handle: str) -> dict:
        raise NotImplementedError("ssh node runtime backend is not implemented yet")

    async def checkpoint_job(self, node: dict, job_handle: str, payload: dict) -> dict:
        raise NotImplementedError("ssh node runtime backend is not implemented yet")

    async def get_checkpoint(self, node: dict, job_handle: str) -> dict:
        raise NotImplementedError("ssh node runtime backend is not implemented yet")

    async def restore_job(self, node: dict, payload: dict) -> dict:
        raise NotImplementedError("ssh node runtime backend is not implemented yet")

    async def terminate_job(self, node: dict, job_handle: str) -> dict:
        raise NotImplementedError("ssh node runtime backend is not implemented yet")


class LocalProcessBackend:
    async def create_reservation(self, node: dict, payload: dict) -> dict:
        raise NotImplementedError("local node runtime backend is not implemented yet")

    async def launch_job(self, node: dict, payload: dict) -> dict:
        raise NotImplementedError("local node runtime backend is not implemented yet")

    async def list_jobs(self, node: dict) -> list[dict]:
        raise NotImplementedError("local node runtime backend is not implemented yet")

    async def get_job(self, node: dict, job_handle: str) -> dict:
        raise NotImplementedError("local node runtime backend is not implemented yet")

    async def pause_job(self, node: dict, job_handle: str) -> dict:
        raise NotImplementedError("local node runtime backend is not implemented yet")

    async def resume_job(self, node: dict, job_handle: str) -> dict:
        raise NotImplementedError("local node runtime backend is not implemented yet")

    async def checkpoint_job(self, node: dict, job_handle: str, payload: dict) -> dict:
        raise NotImplementedError("local node runtime backend is not implemented yet")

    async def get_checkpoint(self, node: dict, job_handle: str) -> dict:
        raise NotImplementedError("local node runtime backend is not implemented yet")

    async def restore_job(self, node: dict, payload: dict) -> dict:
        raise NotImplementedError("local node runtime backend is not implemented yet")

    async def terminate_job(self, node: dict, job_handle: str) -> dict:
        raise NotImplementedError("local node runtime backend is not implemented yet")
