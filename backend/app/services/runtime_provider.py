from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Protocol
ProviderType = Literal["http_local", "http_remote", "ssh_linux"]
AuthType = Literal["password", "private_key"]
@dataclass(frozen=True)
class RuntimeTarget:
    provider_type: ProviderType
    label: str
    agent_url: str | None = None
    host: str | None = None
    port: int | None = None
    username: str | None = None
    auth_type: AuthType | None = None
    sudo_enabled: bool = False
    host_fingerprint: str | None = None
    credential_id: str | None = None
class RuntimeProvider(Protocol):
    async def health_check(self) -> dict | None:
        ...
    async def get_all_gpus(self) -> list[dict]:
        ...
    async def get_training_logs(self) -> list[dict]:
        ...
    async def get_system_detail(self) -> dict | None:
        ...
    async def get_system_info(self) -> dict | None:
        ...
    async def get_processes(self) -> list[dict]:
        ...
    async def set_power_limit(self, gpu_index: int, power_limit: int) -> dict:
        ...
    async def pause_task(self, pid: int) -> dict:
        ...
    async def resume_task(self, pid: int) -> dict:
        ...
    async def terminate_task(self, pid: int) -> dict:
        ...
    async def close(self) -> None:
        ...
