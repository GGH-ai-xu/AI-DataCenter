from __future__ import annotations

import json
import os
import time


LOCAL_MODE = "local"
REMOTE_MODE = "remote"
UNIMPORTED_REASON = "尚未导入任何 GPU"


class ImportContextService:
    def __init__(self, config_path: str, default_local_url: str):
        self.config_path = config_path
        self.default_local_url = default_local_url.rstrip("/")
        self._state = self._empty_state()

    def _empty_state(self) -> dict:
        return {
            "source_mode": LOCAL_MODE,
            "agent_url": self.default_local_url,
            "agent_label": "本机 Agent",
            "provider_type": "http_local",
            "source_label": "本机 Agent",
            "target_summary": self.default_local_url,
            "imported_gpu_indexes": [],
            "imported_at": None,
            "snapshot": {"system": None, "gpus": []},
            "valid": False,
            "invalid_reason": UNIMPORTED_REASON,
        }

    def _ensure_parent(self):
        os.makedirs(os.path.dirname(self.config_path) or ".", exist_ok=True)

    def _persist(self):
        self._ensure_parent()
        with open(self.config_path, "w", encoding="utf-8") as handle:
            json.dump(self._state, handle, ensure_ascii=False, indent=2)

    @staticmethod
    def _normalize_gpu_indexes(gpu_indexes: list[int] | None) -> list[int]:
        if not gpu_indexes:
            return []
        return sorted({int(item) for item in gpu_indexes})

    def _loaded_state(self, payload: dict | None) -> dict:
        state = self._empty_state()
        if not isinstance(payload, dict):
            return state
        state.update(payload)
        state["imported_gpu_indexes"] = self._normalize_gpu_indexes(
            payload.get("imported_gpu_indexes")
        )
        snapshot = payload.get("snapshot")
        if isinstance(snapshot, dict):
            state["snapshot"] = {
                "system": snapshot.get("system"),
                "gpus": list(snapshot.get("gpus") or []),
            }
        return state

    def load(self) -> dict:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                self._state = self._loaded_state(payload)
            except Exception:
                self._state = self._empty_state()
                self._persist()
        else:
            self._state = self._empty_state()
            self._persist()
        return self.snapshot()

    def snapshot(self) -> dict:
        return json.loads(json.dumps(self._state, ensure_ascii=False))

    def selected_gpu_indexes(self) -> list[int]:
        return self._normalize_gpu_indexes(self._state.get("imported_gpu_indexes"))

    @staticmethod
    def _filter_gpus_by_indexes(gpus: list[dict] | None, indexes: list[int]) -> list[dict]:
        selected = set(indexes)
        return [
            gpu for gpu in (gpus or [])
            if int(gpu.get("index", -1)) in selected
        ]

    def save_import(
        self,
        source_mode: str,
        agent_url: str,
        agent_label: str,
        gpu_indexes: list[int],
        system_info: dict | None,
        gpus: list[dict],
        provider_type: str | None = None,
        source_label: str | None = None,
        target_summary: str | None = None,
    ) -> dict:
        selected = self._normalize_gpu_indexes(gpu_indexes)
        mode = REMOTE_MODE if source_mode == REMOTE_MODE else LOCAL_MODE
        default_label = "远程 Agent" if mode == REMOTE_MODE else "本机 Agent"
        resolved_label = (agent_label or "").strip() or default_label
        self._state = {
            "source_mode": mode,
            "agent_url": agent_url.rstrip("/"),
            "agent_label": resolved_label,
            "provider_type": provider_type or ("http_remote" if mode == REMOTE_MODE else "http_local"),
            "source_label": (source_label or "").strip() or resolved_label,
            "target_summary": (target_summary or "").strip() or agent_url.rstrip("/"),
            "imported_gpu_indexes": selected,
            "imported_at": time.time(),
            "snapshot": {
                "system": system_info or None,
                "gpus": self._filter_gpus_by_indexes(gpus, selected),
            },
            "valid": True,
            "invalid_reason": "",
        }
        self._persist()
        return self.snapshot()

    def _mark_valid(self) -> dict:
        was_valid = bool(self._state.get("valid"))
        had_reason = bool(self._state.get("invalid_reason"))
        self._state["valid"] = True
        self._state["invalid_reason"] = ""
        if not was_valid or had_reason:
            self._persist()
        return self.snapshot()

    def clear(self, reason: str = "已清空导入上下文") -> dict:
        next_state = self._empty_state()
        next_state["invalid_reason"] = reason
        if self._state != next_state:
            self._state = next_state
            self._persist()
        return self.snapshot()

    def mark_invalid(self, reason: str) -> dict:
        if self._state.get("valid") or self._state.get("invalid_reason") != reason:
            self._state["valid"] = False
            self._state["invalid_reason"] = reason
            self._persist()
        return self.snapshot()

    def validate_runtime(self, agent_health: dict | None, gpus: list[dict]) -> dict:
        selected = self.selected_gpu_indexes()
        if not agent_health:
            if not selected and not self._state.get("imported_at"):
                return self.snapshot()
            return self.mark_invalid("当前导入目标不可达，需要重新导入")
        if not selected:
            return self._mark_valid()

        found = {int(item.get("index", -1)) for item in gpus or []}
        missing = [index for index in selected if index not in found]
        if missing:
            labels = ", ".join(f"GPU {index}" for index in missing)
            return self.mark_invalid(f"已导入的 {labels} 不再存在")
        unavailable = [
            index
            for index in selected
            if any(
                int(item.get("index", -1)) == index and not item.get("available", True)
                for item in gpus or []
            )
        ]
        if unavailable:
            if len(unavailable) == 1:
                return self.mark_invalid(f"已导入的 GPU {unavailable[0]} 当前不可用")
            labels = ", ".join(f"GPU {index}" for index in unavailable)
            return self.mark_invalid(f"已导入的 {labels} 当前不可用")
        return self._mark_valid()

    def filter_gpus(self, gpus: list[dict] | None) -> list[dict]:
        selected = set(self.selected_gpu_indexes())
        return [
            gpu for gpu in (gpus or [])
            if int(gpu.get("index", -1)) in selected
        ]

    def filter_processes(self, processes: list[dict] | None) -> list[dict]:
        selected = set(self.selected_gpu_indexes())
        return [
            proc for proc in (processes or [])
            if int(proc.get("gpu_index", -1)) in selected
        ]

    def ensure_gpu_allowed(self, gpu_index: int):
        if int(gpu_index) not in set(self.selected_gpu_indexes()):
            raise ValueError(f"GPU {gpu_index} 不在当前导入范围内，请重新导入管理卡")

    def ensure_process_allowed(self, pid: int, processes: list[dict]):
        allowed = {
            int(proc.get("pid", -1))
            for proc in self.filter_processes(processes)
        }
        if int(pid) not in allowed:
            raise ValueError(f"PID {pid} 不在当前导入范围内，请重新导入管理卡")
