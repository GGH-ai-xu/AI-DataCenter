from __future__ import annotations

import json
import os
import secrets

from cryptography.fernet import InvalidToken


MASK = "********"
MASTER_KEY_ENV = "GPU_GOV_MASTER_KEY"


class CredentialStore:
    def __init__(self, config_path: str, cipher=None):
        self.config_path = config_path
        self.cipher = cipher
        self._data = self._load()

    def _load(self) -> dict[str, dict]:
        if not os.path.exists(self.config_path):
            return {}
        with open(self.config_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("credential store payload must be an object")
        return {
            str(key): dict(value)
            for key, value in payload.items()
            if isinstance(value, dict)
        }

    def _persist(self) -> None:
        parent = os.path.dirname(self.config_path) or "."
        os.makedirs(parent, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as handle:
            json.dump(self._data, handle, ensure_ascii=False, indent=2)

    def _require_cipher(self):
        if self.cipher is None:
            raise ValueError(f"平台未配置主密钥 {MASTER_KEY_ENV}，无法保存或读取 SSH 凭据")

    def save(self, payload: dict) -> str:
        self._require_cipher()
        credential_id = str(payload.get("credential_id") or secrets.token_hex(12))
        self._data[credential_id] = {
            str(key): self.cipher.encrypt(str(value))
            for key, value in payload.items()
            if key != "credential_id" and value
        }
        self._persist()
        return credential_id

    def read(self, credential_id: str) -> dict:
        self._require_cipher()
        stored = dict(self._data.get(str(credential_id), {}))
        try:
            return {
                key: self.cipher.decrypt(value)
                for key, value in stored.items()
            }
        except InvalidToken as exc:
            raise ValueError("已保存 SSH 凭据无法用当前主密钥解密") from exc

    def delete(self, credential_id: str) -> None:
        self._data.pop(str(credential_id), None)
        self._persist()

    def masked_snapshot(self, credential_id: str) -> dict:
        return {
            key: MASK
            for key in self._data.get(str(credential_id), {})
        }
