"""接入配置服务 - 管理本机/远程 Agent 接入方式"""

from __future__ import annotations

import json
import os
import time
from urllib.parse import urlparse

import httpx


LOCAL_MODE = "local"
REMOTE_MODE = "remote"
DEFAULT_AGENT_PORT = 8001


class ConnectionSettingsService:
    """持久化并应用 Agent 接入配置。"""

    def __init__(self, config_path: str, default_local_url: str):
        self.config_path = config_path
        self.default_local_url = self.normalize_agent_url(default_local_url)
        self._state = {
            "mode": LOCAL_MODE,
            "agent_url": self.default_local_url,
            "agent_label": "本机 Agent",
            "updated_at": None,
        }

    @staticmethod
    def normalize_agent_url(value: str) -> str:
        raw = (value or "").strip()
        if not raw:
            raise ValueError("Agent 地址不能为空")
        if "://" not in raw:
            raw = f"http://{raw}"

        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Agent 地址只支持 http 或 https")
        if not parsed.netloc or not parsed.hostname:
            raise ValueError("Agent 地址格式无效")
        if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
            raise ValueError("Agent 地址不能包含额外路径、参数或锚点")

        host = parsed.hostname
        port = parsed.port or DEFAULT_AGENT_PORT
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"

        return f"{parsed.scheme}://{host}:{port}".rstrip("/")

    def _ensure_parent(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

    def _persist(self):
        self._ensure_parent()
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2)

    def _apply_loaded_state(self, payload: dict | None):
        if not isinstance(payload, dict):
            return

        mode = payload.get("mode", LOCAL_MODE)
        agent_label = (payload.get("agent_label") or "").strip()
        agent_url = payload.get("agent_url") or self.default_local_url

        if mode not in {LOCAL_MODE, REMOTE_MODE}:
            mode = LOCAL_MODE
        if mode == LOCAL_MODE:
            agent_url = self.default_local_url
            agent_label = agent_label or "本机 Agent"
        else:
            agent_url = self.normalize_agent_url(agent_url)
            agent_label = agent_label or "远程 Agent"

        self._state = {
            "mode": mode,
            "agent_url": agent_url,
            "agent_label": agent_label,
            "updated_at": float(payload.get("updated_at") or time.time()),
        }

    def load(self) -> dict:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                self._apply_loaded_state(payload)
            except Exception:
                self._state = {
                    "mode": LOCAL_MODE,
                    "agent_url": self.default_local_url,
                    "agent_label": "本机 Agent",
                    "updated_at": time.time(),
                }
                self._persist()
        else:
            self._state["updated_at"] = time.time()
            self._persist()
        return dict(self._state)

    def resolve_target(self, mode: str, agent_url: str | None) -> tuple[str, str]:
        selected_mode = mode if mode in {LOCAL_MODE, REMOTE_MODE} else LOCAL_MODE
        if selected_mode == LOCAL_MODE:
            return selected_mode, self.default_local_url
        return selected_mode, self.normalize_agent_url(agent_url or "")

    async def probe(self, target_url: str) -> dict | None:
        try:
            async with httpx.AsyncClient(base_url=target_url, timeout=8.0) as client:
                resp = await client.get("/api/health")
                resp.raise_for_status()
                data = resp.json()
                return data if isinstance(data, dict) else None
        except Exception:
            return None

    def snapshot(self, agent_health: dict | None = None) -> dict:
        connected = bool(agent_health and agent_health.get("status") == "ok")
        return {
            "mode": self._state["mode"],
            "mode_label": "本机模式" if self._state["mode"] == LOCAL_MODE else "远程服务器模式",
            "agent_url": self._state["agent_url"],
            "agent_label": self._state["agent_label"],
            "connected": connected,
            "updated_at": self._state["updated_at"],
            "default_local_url": self.default_local_url,
            "target_hint": (
                "使用当前电脑上的 Agent 采集与执行"
                if self._state["mode"] == LOCAL_MODE
                else "连接指定服务器上的 Agent 采集与执行"
            ),
            "agent_health": agent_health,
        }

    async def update(self, agent_client, mode: str, agent_url: str | None, agent_label: str | None) -> dict:
        selected_mode, resolved_url = self.resolve_target(mode, agent_url)
        label = (agent_label or "").strip()
        if not label:
            label = "本机 Agent" if selected_mode == LOCAL_MODE else "远程 Agent"

        self._state = {
            "mode": selected_mode,
            "agent_url": resolved_url,
            "agent_label": label,
            "updated_at": time.time(),
        }
        self._persist()

        await agent_client.reconfigure(resolved_url)
        health = await agent_client.health_check()
        return self.snapshot(health)
