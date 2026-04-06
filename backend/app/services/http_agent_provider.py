from __future__ import annotations

from app.services.agent_client import AgentClient
from app.services.runtime_provider import RuntimeTarget


class HttpAgentProvider:
    def __init__(self, target: RuntimeTarget):
        if not target.agent_url:
            raise ValueError("HTTP provider requires agent_url")
        self.target = target
        self.client = AgentClient(target.agent_url)

    async def health_check(self) -> dict | None:
        return await self.client.health_check()

    async def get_all_gpus(self) -> list[dict]:
        return await self.client.get_all_gpus()

    async def get_training_logs(self) -> list[dict]:
        return await self.client.get_training_logs()

    async def get_system_detail(self) -> dict | None:
        return await self.client.get_system_detail()

    async def get_system_info(self) -> dict | None:
        return await self.client.get_system_info()

    async def get_processes(self) -> list[dict]:
        return await self.client.get_processes()

    async def set_power_limit(self, gpu_index: int, power_limit: int) -> dict:
        return await self.client.set_power_limit(gpu_index, power_limit)

    async def pause_task(self, pid: int) -> dict:
        return await self.client.pause_task(pid)

    async def resume_task(self, pid: int) -> dict:
        return await self.client.resume_task(pid)

    async def terminate_task(self, pid: int) -> dict:
        return await self.client.terminate_task(pid)

    async def close(self) -> None:
        await self.client.close()
