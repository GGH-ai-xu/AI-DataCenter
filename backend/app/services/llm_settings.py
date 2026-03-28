"""LLM 运行时配置服务 - 支持页面在线配置与热更新"""

from __future__ import annotations

import json
import logging
import os
import time
from urllib.parse import urlparse

from openai import AsyncOpenAI

from app.services.llm import LLMService


logger = logging.getLogger(__name__)

DEFAULT_LLM_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_LLM_MODEL = "deepseek-chat"
PLACEHOLDER_API_KEY = "sk-your-key-here"


class LLMSettingsService:
    """持久化并应用 LLM 运行时配置。"""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self._state = self._build_default_state()

    @staticmethod
    def normalize_base_url(value: str) -> str:
        raw = (value or "").strip()
        if not raw:
            raise ValueError("LLM 接口地址不能为空")
        if "://" not in raw:
            raw = f"https://{raw}"

        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("LLM 接口地址只支持 http 或 https")
        if not parsed.netloc or not parsed.hostname:
            raise ValueError("LLM 接口地址格式无效")
        if parsed.params or parsed.query or parsed.fragment:
            raise ValueError("LLM 接口地址不能包含查询参数或锚点")

        path = parsed.path.rstrip("/")
        return f"{parsed.scheme}://{parsed.netloc}{path}"

    @staticmethod
    def mask_api_key(value: str) -> str:
        key = (value or "").strip()
        if not key:
            return ""
        if len(key) <= 10:
            return "*" * len(key)
        return f"{key[:6]}***{key[-4:]}"

    def _build_default_state(self) -> dict:
        env_base_url = os.getenv("LLM_BASE_URL", DEFAULT_LLM_BASE_URL)
        env_model = (os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL) or DEFAULT_LLM_MODEL).strip()
        env_api_key = (os.getenv("LLM_API_KEY", "") or "").strip()

        if env_api_key == PLACEHOLDER_API_KEY:
            env_api_key = ""

        try:
            base_url = self.normalize_base_url(env_base_url)
        except ValueError:
            base_url = DEFAULT_LLM_BASE_URL

        return {
            "enabled": bool(env_api_key),
            "base_url": base_url,
            "model": env_model or DEFAULT_LLM_MODEL,
            "api_key": env_api_key,
            "updated_at": None,
            "source": (
                "env"
                if any(os.getenv(name) for name in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"))
                else "default"
            ),
        }

    def _ensure_parent(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

    def _persist(self):
        self._ensure_parent()
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2)

    def _merge_loaded_state(self, payload: dict | None) -> dict:
        state = self._build_default_state()
        if not isinstance(payload, dict):
            return state

        raw_base_url = payload.get("base_url", state["base_url"])
        raw_model = payload.get("model", state["model"])
        raw_enabled = payload.get("enabled", state["enabled"])
        raw_api_key = payload.get("api_key", state["api_key"])

        try:
            base_url = self.normalize_base_url(raw_base_url)
        except ValueError:
            base_url = state["base_url"]

        api_key = (raw_api_key or "").strip()
        if api_key == PLACEHOLDER_API_KEY:
            api_key = ""

        return {
            "enabled": bool(raw_enabled),
            "base_url": base_url,
            "model": (raw_model or state["model"] or DEFAULT_LLM_MODEL).strip() or DEFAULT_LLM_MODEL,
            "api_key": api_key,
            "updated_at": float(payload.get("updated_at") or time.time()),
            "source": "runtime",
        }

    def load(self) -> dict:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                self._state = self._merge_loaded_state(payload)
            except Exception as exc:
                logger.warning("加载 LLM 运行时配置失败，回退默认配置: %s", exc)
                self._state = self._build_default_state()
        else:
            self._state = self._build_default_state()
        return dict(self._state)

    def _snapshot_from_state(self, state: dict, llm_available: bool | None = None) -> dict:
        has_api_key = bool(state.get("api_key"))
        enabled = bool(state.get("enabled"))
        return {
            "enabled": enabled,
            "base_url": state.get("base_url", DEFAULT_LLM_BASE_URL),
            "model": state.get("model", DEFAULT_LLM_MODEL),
            "has_api_key": has_api_key,
            "api_key_masked": self.mask_api_key(state.get("api_key", "")),
            "updated_at": state.get("updated_at"),
            "source": state.get("source", "default"),
            "llm_available": (enabled and has_api_key) if llm_available is None else bool(llm_available),
        }

    def snapshot(self, llm_available: bool | None = None) -> dict:
        return self._snapshot_from_state(self._state, llm_available)

    def resolve_candidate(
        self,
        base_url: str | None,
        model: str | None,
        api_key: str | None,
        keep_existing_key: bool = True,
    ) -> dict:
        resolved_base_url = self.normalize_base_url(
            base_url or self._state.get("base_url") or DEFAULT_LLM_BASE_URL
        )
        provided_model = (model or "").strip()
        if provided_model:
            resolved_model = provided_model
        elif self._state.get("api_key") or self._state.get("enabled") or self._state.get("source") != "default":
            resolved_model = (self._state.get("model") or "").strip() or DEFAULT_LLM_MODEL
        else:
            resolved_model = ""

        candidate_key = (api_key or "").strip()
        if candidate_key:
            resolved_api_key = candidate_key
        elif keep_existing_key:
            resolved_api_key = (self._state.get("api_key") or "").strip()
        else:
            resolved_api_key = ""

        if resolved_api_key == PLACEHOLDER_API_KEY:
            resolved_api_key = ""

        return {
            "enabled": True,
            "base_url": resolved_base_url,
            "model": resolved_model,
            "api_key": resolved_api_key,
            "updated_at": time.time(),
            "source": "runtime",
        }

    async def _detect_model(self, base_url: str, api_key: str) -> str | None:
        try:
            client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            response = await client.models.list()
        except Exception as exc:
            logger.warning("自动探测模型失败: %s", exc)
            return None

        for item in getattr(response, "data", []) or []:
            model_id = getattr(item, "id", None)
            if not model_id and isinstance(item, dict):
                model_id = item.get("id")
            if model_id:
                return str(model_id)
        return None

    async def validate_candidate(self, candidate: dict) -> dict:
        api_key = (candidate.get("api_key") or "").strip()
        if not api_key:
            raise ValueError("请提供 API Key，或保留当前已保存的 Key")

        model = (candidate.get("model") or "").strip()
        if not model:
            model = await self._detect_model(candidate["base_url"], api_key)
            if not model:
                raise ValueError("未提供模型名，且无法从接口自动探测，请手动填写 Model")

        try:
            client = AsyncOpenAI(api_key=api_key, base_url=candidate["base_url"])
            await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                temperature=0,
                max_tokens=8,
            )
        except Exception as exc:
            raise ValueError(f"LLM 连接测试失败：{exc}") from exc

        validated = dict(candidate)
        validated["model"] = model
        return validated

    async def test(
        self,
        base_url: str | None,
        model: str | None,
        api_key: str | None,
        keep_existing_key: bool = True,
    ) -> dict:
        candidate = self.resolve_candidate(base_url, model, api_key, keep_existing_key)
        validated = await self.validate_candidate(candidate)
        return {
            "success": True,
            "message": "LLM 连接成功",
            "llm": self._snapshot_from_state(validated, llm_available=True),
        }

    async def update(
        self,
        enabled: bool,
        base_url: str | None,
        model: str | None,
        api_key: str | None,
        keep_existing_key: bool = True,
    ) -> tuple[dict, LLMService | None]:
        candidate = self.resolve_candidate(base_url, model, api_key, keep_existing_key)
        candidate["enabled"] = bool(enabled)

        if candidate["enabled"]:
            candidate = await self.validate_candidate(candidate)

        self._state = {
            **candidate,
            "updated_at": time.time(),
            "source": "runtime",
        }
        self._persist()
        llm_service = self.build_service()
        return self.snapshot(llm_service is not None), llm_service

    def build_service(self) -> LLMService | None:
        if not self._state.get("enabled"):
            return None

        api_key = (self._state.get("api_key") or "").strip()
        base_url = (self._state.get("base_url") or "").strip()
        model = (self._state.get("model") or "").strip()
        if not api_key or not base_url or not model:
            return None

        return LLMService(api_key=api_key, base_url=base_url, model=model)
