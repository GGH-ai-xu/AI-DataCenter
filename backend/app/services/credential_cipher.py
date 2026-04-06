from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet


MASTER_KEY_ENV = "GPU_GOV_MASTER_KEY"


class CredentialCipher:
    def __init__(self, master_key: str):
        normalized = str(master_key or "").strip()
        if not normalized:
            raise ValueError(f"平台未配置主密钥 {MASTER_KEY_ENV}")
        digest = hashlib.sha256(normalized.encode("utf-8")).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(str(value).encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str) -> str:
        return self._fernet.decrypt(str(value).encode("utf-8")).decode("utf-8")
