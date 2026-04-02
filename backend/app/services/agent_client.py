"""Agent通信客户端 - 通过HTTP与GPU服务器Agent交互"""

import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class AgentClient:
    """与GPU服务器Agent通信的HTTP客户端"""

    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        async with self._client_lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.AsyncClient(
                    base_url=self.base_url,
                    timeout=self.timeout,
                    trust_env=False,
                )
            return self._client

    async def close(self):
        async with self._client_lock:
            if self._client and not self._client.is_closed:
                await self._client.aclose()

    @staticmethod
    def _extract_http_error(e: httpx.HTTPStatusError) -> str:
        try:
            payload = e.response.json()
            if isinstance(payload, dict) and payload.get("detail"):
                return str(payload.get("detail"))
        except Exception:
            pass

        text = (e.response.text or "").strip()
        return text or str(e)

    async def reconfigure(self, base_url: str, timeout: float | None = None):
        async with self._client_lock:
            if self._client and not self._client.is_closed:
                await self._client.aclose()
            self.base_url = base_url.rstrip("/")
            if timeout is not None:
                self.timeout = timeout
            self._client = None

    async def health_check(self) -> Optional[dict]:
        try:
            client = await self._get_client()
            resp = await client.get("/api/health")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Agent健康检查失败: {e}")
            return None

    async def get_all_gpus(self) -> list[dict]:
        try:
            client = await self._get_client()
            resp = await client.get("/api/gpus")
            resp.raise_for_status()
            gpus = resp.json().get("gpus", [])
            if not isinstance(gpus, list):
                logger.error(f"Agent返回的GPU数据格式异常: {type(gpus)}")
                return []
            return gpus
        except Exception as e:
            logger.error(f"获取GPU数据失败: {e}")
            return []

    async def get_system_info(self) -> Optional[dict]:
        try:
            client = await self._get_client()
            resp = await client.get("/api/system")
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict):
                return None
            return data
        except Exception:
            return None

    async def get_processes(self) -> list[dict]:
        try:
            client = await self._get_client()
            resp = await client.get("/api/processes")
            resp.raise_for_status()
            procs = resp.json().get("processes", [])
            if not isinstance(procs, list):
                return []
            return procs
        except Exception:
            return []

    async def set_power_limit(self, gpu_index: int, power_limit: int) -> dict:
        try:
            client = await self._get_client()
            resp = await client.post(
                "/api/power-limit",
                json={"gpu_index": gpu_index, "power_limit": power_limit},
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            return {"success": False, "error": self._extract_http_error(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def pause_task(self, pid: int) -> dict:
        try:
            client = await self._get_client()
            resp = await client.post("/api/task/pause", json={"pid": pid})
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            return {"success": False, "error": self._extract_http_error(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def resume_task(self, pid: int) -> dict:
        try:
            client = await self._get_client()
            resp = await client.post("/api/task/resume", json={"pid": pid})
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            return {"success": False, "error": self._extract_http_error(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def terminate_task(self, pid: int) -> dict:
        try:
            client = await self._get_client()
            resp = await client.post("/api/task/terminate", json={"pid": pid})
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            return {"success": False, "error": self._extract_http_error(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_system_detail(self) -> Optional[dict]:
        """获取完整系统信息（含磁盘、网络、每核CPU）"""
        try:
            client = await self._get_client()
            resp = await client.get("/api/system/detail")
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict):
                return None
            return data
        except Exception:
            return None

    async def get_training_logs(self) -> list[dict]:
        """获取训练日志和指标"""
        try:
            client = await self._get_client()
            resp = await client.get("/api/training/logs")
            resp.raise_for_status()
            logs = resp.json().get("training", [])
            if not isinstance(logs, list):
                return []
            return logs
        except Exception:
            return []
