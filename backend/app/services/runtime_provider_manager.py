from __future__ import annotations

import asyncio


class RuntimeProviderManager:
    def __init__(self, factory, reconnect_limit: int = 6):
        self._factory = factory
        self._lock = asyncio.Lock()
        self._provider = None
        self._target = None
        self._secret = {}
        self._status = "idle"
        self._last_error = ""
        self._reconnect_limit = reconnect_limit
        self._reconnect_failures = 0

    async def switch(self, target, secret):
        next_provider = await self._factory(target, secret)
        async with self._lock:
            previous = self._provider
            self._provider = next_provider
            self._target = target
            self._secret = dict(secret or {})
            self._status = "connected"
            self._last_error = ""
            self._reconnect_failures = 0
        if previous:
            await previous.close()
        return next_provider

    async def probe_target(self, target, secret):
        provider = await self._factory(target, secret)
        try:
            capability_reader = getattr(provider, "capabilities_snapshot", None)
            capabilities = capability_reader() if callable(capability_reader) else {}
            try:
                health = await provider.health_check()
                system = await provider.get_system_info() if health else None
                gpus = await provider.get_all_gpus() if health else []
            except Exception as exc:
                return {
                    "status": "offline",
                    "health": None,
                    "system": None,
                    "gpus": [],
                    "capabilities": capabilities,
                    "error": str(exc),
                }
            return {
                "status": "connected" if health else "offline",
                "health": health,
                "system": system,
                "gpus": gpus,
                "capabilities": capabilities,
            }
        finally:
            await provider.close()

    async def current_provider(self):
        if self._provider is None:
            raise RuntimeError("runtime provider is not configured")
        return self._provider

    async def reconnect(self) -> dict:
        async with self._lock:
            target = self._target
            secret = dict(self._secret)
        if target is None:
            raise RuntimeError("runtime provider target is not configured")

        candidate = None
        try:
            candidate = await self._factory(target, secret)
            health = await candidate.health_check()
            if not health:
                raise RuntimeError("runtime provider health check failed")
        except Exception as exc:
            if candidate is not None:
                await candidate.close()
            return await self.mark_failure(str(exc))

        async with self._lock:
            previous = self._provider
            self._provider = candidate
            self._status = "connected"
            self._last_error = ""
            self._reconnect_failures = 0
        if previous:
            await previous.close()
        return await self.status()

    async def record_success(self) -> dict:
        async with self._lock:
            self._status = "connected"
            self._last_error = ""
            self._reconnect_failures = 0
        return await self.status()

    async def status(self) -> dict:
        target = self._target
        return {
            "status": self._status,
            "connected": self._status == "connected",
            "provider_type": getattr(target, "provider_type", ""),
            "label": getattr(target, "label", ""),
            "target": self._public_target(target),
            "last_error": self._last_error,
            "reconnect_failures": self._reconnect_failures,
        }

    async def mark_failure(self, reason: str) -> dict:
        async with self._lock:
            self._reconnect_failures += 1
            self._last_error = reason
            if self._reconnect_failures >= self._reconnect_limit:
                self._status = "invalid"
            else:
                self._status = "reconnecting"
        return await self.status()

    def _public_target(self, target) -> dict | None:
        if target is None:
            return None
        return {
            "provider_type": target.provider_type,
            "label": target.label,
            "agent_url": target.agent_url,
            "host": target.host,
            "port": target.port,
            "username": target.username,
            "auth_type": target.auth_type,
            "sudo_enabled": target.sudo_enabled,
            "host_fingerprint": target.host_fingerprint,
            "credential_id": target.credential_id,
        }
