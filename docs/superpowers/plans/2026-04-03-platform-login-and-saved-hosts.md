# Platform Login And Saved Hosts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为平台新增真实的用户名密码登录、管理员手动创建用户、基于平台会话的鉴权，以及“按用户保存 SSH 主机并用主密钥加密凭据”的免密码重连导入能力。

**Architecture:** 后端新增独立的平台身份域，使用 `PlatformIdentityStore + PlatformAuthService + SavedHostService` 管理用户、会话与主机归属；现有导入链路通过 `saved_host_id` 复用已保存目标。前端新增 `auth store + /login + /change-password`，并把 `/import` 扩展为“已保存主机 / 新建连接 / 硬件概览 / 选卡导入”四阶段工作台，同时用平台会话保护 REST 与 WebSocket。

**Tech Stack:** FastAPI、Starlette middleware、aiosqlite、Python `hashlib.scrypt`、`cryptography` Fernet、Vue 3、Pinia、Vue Router、Axios、Node `node:test`、Python `unittest` / `pytest`。

---

## Implementation Assumptions

- 默认管理员用户名固定为 `admin`。
- 首次启动时若用户表为空，后端生成一次性随机初始密码并打印到后端日志；密码只存哈希，不明文落盘。
- 主密钥环境变量名固定为 `GPU_GOV_MASTER_KEY`。
- 平台会话继续使用 `Authorization: Bearer <token>` 头，便于复用现有 Axios 注入逻辑。
- WebSocket 握手使用 `ws://.../ws?token=<session_token>`，复用现有 query token 语义。
- `saved_hosts` 支持所有 provider 类型，但“免输 SSH 密码”只对 `ssh_linux` 有意义。

## File Map

**Create:**
- `backend/app/api/auth.py`
  Purpose: expose login, logout, me, and change-password APIs.
- `backend/app/api/admin_users.py`
  Purpose: expose admin-only create-user, list-users, and reset-password APIs.
- `backend/app/api/hosts.py`
  Purpose: expose saved-host listing and deletion APIs.
- `backend/app/api/auth_access.py`
  Purpose: centralize `require_authenticated_user()` and `require_admin_user()` helpers for routes.
- `backend/app/services/password_hasher.py`
  Purpose: hash and verify platform passwords with `hashlib.scrypt`.
- `backend/app/services/platform_identity_store.py`
  Purpose: own SQLite tables and CRUD for users, sessions, and saved hosts.
- `backend/app/services/platform_auth_service.py`
  Purpose: bootstrap default admin, create/revoke sessions, change/reset passwords, and resolve session tokens.
- `backend/app/services/saved_host_service.py`
  Purpose: enforce owner/admin visibility, upsert saved hosts, and resolve `saved_host_id` into runtime target + decrypted credentials.
- `backend/app/services/credential_cipher.py`
  Purpose: derive a Fernet key from `GPU_GOV_MASTER_KEY` and encrypt/decrypt credential fields.
- `tests/test_platform_identity_flow.py`
  Purpose: lock default-admin bootstrap, login/logout/change-password, and session recovery behavior.
- `tests/test_saved_host_service.py`
  Purpose: lock owner/admin visibility, host deletion, and `saved_host_id` resolution behavior.
- `tests/test_encrypted_credential_store.py`
  Purpose: ensure credential JSON never stores plaintext and that missing/invalid master keys fail explicitly.
- `frontend/src/stores/auth.js`
  Purpose: own session token, current user, restore/login/logout/change-password lifecycle.
- `frontend/src/stores/auth.test.js`
  Purpose: lock auth-store hydration and session persistence behavior.
- `frontend/src/lib/authSession.js`
  Purpose: centralize localStorage key and token read/write helpers.
- `frontend/src/lib/routeAccess.js`
  Purpose: keep route and layout gating logic pure and testable.
- `frontend/src/lib/routeAccess.test.js`
  Purpose: lock redirect rules for anonymous, must-change-password, and workspace-locked states.
- `frontend/src/views/LoginView.vue`
  Purpose: render standalone login page.
- `frontend/src/views/ChangePasswordView.vue`
  Purpose: render standalone forced password-change page.
- `frontend/src/composables/useSavedHosts.js`
  Purpose: keep saved-host list/scan/delete state out of `ImportWorkspace.vue`.
- `frontend/src/components/import/ImportSavedHostsStage.vue`
  Purpose: render “我的主机 / 全部主机” list and direct-scan actions.

**Modify:**
- `backend/requirements.txt`
  Purpose: add `cryptography` dependency for credential encryption.
- `backend/app/main.py`
  Purpose: initialize identity/auth/saved-host services, register new routers, log bootstrap admin password, and gate WebSocket by session token.
- `backend/app/models/schemas.py`
  Purpose: add auth/admin/saved-host request schemas and extend import requests with `saved_host_id`.
- `backend/app/middleware/auth.py`
  Purpose: switch from static-token-only auth to session-first auth while keeping legacy token compatibility.
- `backend/app/api/system.py`
  Purpose: resolve `saved_host_id`, reuse decrypted credentials, and upsert saved-host records after successful import.
- `backend/app/services/credential_store.py`
  Purpose: require encrypted read/write when handling secrets and add `delete()` support for host removal.
- `backend/tests/test_auth.py`
  Purpose: lock new auth middleware constants and session-first token resolution behavior.
- `tests/test_credential_store.py`
  Purpose: replace plaintext assertions with encrypted persistence assertions.
- `tests/test_ssh_import_flow.py`
  Purpose: cover `saved_host_id` scan/import paths and permission errors.
- `tests/test_import_layer_structure.py`
  Purpose: assert `/import` now includes `已保存主机` stage.
- `tests/test_frontend_ui_structure.py`
  Purpose: assert auth routes and auth-shell layout are present.
- `frontend/src/main.js`
  Purpose: register `/login` and `/change-password`, hydrate auth before navigation, and enforce route guards.
- `frontend/src/App.vue`
  Purpose: split auth-shell vs import-shell vs console-shell and only start workspace polling/WebSocket when authenticated.
- `frontend/src/services/api.js`
  Purpose: swap static token storage to session token helpers and add auth/admin/hosts APIs.
- `frontend/src/composables/useWebSocket.js`
  Purpose: pass session token in the WebSocket URL and stop reconnecting when logged out.
- `frontend/src/stores/app.js`
  Purpose: expose a reset helper so logout clears runtime/import context.
- `frontend/src/views/ImportWorkspace.vue`
  Purpose: add saved-host stage and orchestrate direct scan/import via `saved_host_id`.
- `frontend/src/lib/importWorkbench.js`
  Purpose: add the new stage tab and helper functions for saved-host summaries.
- `frontend/src/components/import/ImportPrepTabs.vue`
  Purpose: update aria label and stage rendering for the fourth tab.

**Verify:**
- `frontend/package.json`
  Purpose: existing `npm test` / `npm run build` entry points used for frontend verification.

---

### Task 1: Define Red Tests For Platform Identity And Encrypted Credentials

**Files:**
- Create: `tests/test_platform_identity_flow.py`
- Create: `tests/test_encrypted_credential_store.py`
- Modify: `tests/test_credential_store.py`
- Test: `tests/test_platform_identity_flow.py`
- Test: `tests/test_encrypted_credential_store.py`
- Test: `tests/test_credential_store.py`

- [ ] **Step 1: Write failing identity-flow tests**

Create `tests/test_platform_identity_flow.py`:

```python
import os
import sys
import tempfile
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.platform_identity_store import PlatformIdentityStore  # noqa: E402
from app.services.platform_auth_service import PlatformAuthService  # noqa: E402


class PlatformIdentityFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tempdir.name, "platform.db")
        self.store = PlatformIdentityStore(self.db_path)
        await self.store.init()
        self.auth = PlatformAuthService(self.store)

    async def asyncTearDown(self):
        await self.store.close()
        self.tempdir.cleanup()

    async def test_bootstrap_default_admin_creates_forced_password_change_user(self):
        notice = await self.auth.ensure_default_admin()
        admin = await self.store.get_user_by_username("admin")

        self.assertEqual(admin["username"], "admin")
        self.assertEqual(admin["role"], "admin")
        self.assertTrue(admin["must_change_password"])
        self.assertTrue(notice["generated_password"])

    async def test_login_returns_session_token_and_persists_session_hash(self):
        notice = await self.auth.ensure_default_admin()

        result = await self.auth.login("admin", notice["generated_password"])
        session = await self.store.get_session_by_token(result["token"])

        self.assertEqual(result["user"]["username"], "admin")
        self.assertTrue(result["user"]["must_change_password"])
        self.assertIsNotNone(session)
        self.assertEqual(session["user_id"], result["user"]["id"])

    async def test_change_password_allows_subsequent_login_with_new_password(self):
        notice = await self.auth.ensure_default_admin()
        login = await self.auth.login("admin", notice["generated_password"])

        await self.auth.change_password(
            user_id=login["user"]["id"],
            current_password=notice["generated_password"],
            new_password="NewPassw0rd!",
        )

        relogin = await self.auth.login("admin", "NewPassw0rd!")
        self.assertFalse(relogin["user"]["must_change_password"])

    async def test_logout_revokes_session(self):
        notice = await self.auth.ensure_default_admin()
        login = await self.auth.login("admin", notice["generated_password"])

        await self.auth.logout(login["token"])
        current = await self.auth.resolve_session(login["token"])

        self.assertIsNone(current)

    async def test_admin_can_create_user_and_reset_password(self):
        notice = await self.auth.ensure_default_admin()
        await self.auth.login("admin", notice["generated_password"])

        created = await self.auth.create_user(
            username="alice",
            password="TempPassw0rd!",
            role="member",
            must_change_password=True,
        )
        await self.auth.reset_password(
            user_id=created["id"],
            password="ResetPassw0rd!",
            must_change_password=True,
        )

        relogin = await self.auth.login("alice", "ResetPassw0rd!")
        self.assertEqual(relogin["user"]["username"], "alice")
        self.assertTrue(relogin["user"]["must_change_password"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Write failing encrypted-credential tests**

Create `tests/test_encrypted_credential_store.py` and update `tests/test_credential_store.py` to reflect encrypted persistence:

```python
import json
import os
import sys
import tempfile
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.credential_cipher import CredentialCipher  # noqa: E402
from app.services.credential_store import CredentialStore  # noqa: E402


class EncryptedCredentialStoreTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.secret_path = os.path.join(self.tempdir.name, "credentials.json")
        self.cipher = CredentialCipher("unit-test-master-key")
        self.store = CredentialStore(self.secret_path, self.cipher)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_persisted_json_does_not_store_plaintext_passwords(self):
        credential_id = self.store.save({
            "password": "secret",
            "sudo_password": "rootpw",
        })

        raw_text = open(self.secret_path, "r", encoding="utf-8").read()
        restored = self.store.read(credential_id)

        self.assertNotIn("secret", raw_text)
        self.assertNotIn("rootpw", raw_text)
        self.assertEqual(restored["password"], "secret")
        self.assertEqual(restored["sudo_password"], "rootpw")

    def test_missing_cipher_raises_explicit_error(self):
        store = CredentialStore(self.secret_path, None)

        with self.assertRaisesRegex(ValueError, "GPU_GOV_MASTER_KEY"):
            store.save({"password": "secret"})


if __name__ == "__main__":
    unittest.main()
```

Replace the plaintext assertions in `tests/test_credential_store.py` with:

```python
        self.cipher = CredentialCipher("unit-test-master-key")
        self.store = CredentialStore(self.secret_path, self.cipher)
```

and:

```python
        raw_text = open(self.secret_path, "r", encoding="utf-8").read()
        self.assertNotIn("secret", raw_text)
        self.assertNotIn("rootpw", raw_text)
```

- [ ] **Step 3: Run the backend red tests and verify they fail for the right reason**

Run:

```bash
timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m unittest tests.test_platform_identity_flow tests.test_encrypted_credential_store tests.test_credential_store -v"
```

Expected:

- FAIL because `PlatformIdentityStore`, `PlatformAuthService`, and `CredentialCipher` do not exist yet
- FAIL because `CredentialStore` does not accept a cipher and still stores plaintext

- [ ] **Step 4: Commit the red tests**

```bash
git add tests/test_platform_identity_flow.py tests/test_encrypted_credential_store.py tests/test_credential_store.py
git commit -m "test: define platform identity and credential encryption"
```

---

### Task 2: Implement Password Hashing, Identity Persistence, And Encrypted Credential Storage

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/services/password_hasher.py`
- Create: `backend/app/services/credential_cipher.py`
- Create: `backend/app/services/platform_identity_store.py`
- Create: `backend/app/services/platform_auth_service.py`
- Modify: `backend/app/services/credential_store.py`
- Modify: `backend/app/main.py`
- Test: `tests/test_platform_identity_flow.py`
- Test: `tests/test_encrypted_credential_store.py`
- Test: `tests/test_credential_store.py`

- [ ] **Step 1: Add the encryption dependency**

Append to `backend/requirements.txt`:

```text
cryptography==43.0.1
```

- [ ] **Step 2: Implement password hashing and credential encryption helpers**

Create `backend/app/services/password_hasher.py`:

```python
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets


SCRYPT_N = 2 ** 14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SALT_BYTES = 16


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    return "scrypt${}${}${}${}${}".format(
        SCRYPT_N,
        SCRYPT_R,
        SCRYPT_P,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, stored_hash: str) -> bool:
    _, n_text, r_text, p_text, salt_text, digest_text = stored_hash.split("$", 5)
    salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
    expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
    actual = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=int(n_text),
        r=int(r_text),
        p=int(p_text),
        dklen=len(expected),
    )
    return hmac.compare_digest(actual, expected)
```

Create `backend/app/services/credential_cipher.py`:

```python
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet


class CredentialCipher:
    def __init__(self, master_key: str):
        normalized = str(master_key or "").strip()
        if not normalized:
            raise ValueError("平台未配置主密钥 GPU_GOV_MASTER_KEY")
        digest = hashlib.sha256(normalized.encode("utf-8")).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str) -> str:
        return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")
```

- [ ] **Step 3: Implement identity store, auth service, and encrypted credential store**

Create `backend/app/services/platform_identity_store.py`:

```python
from __future__ import annotations

import hashlib
import os
import time
from typing import Optional

import aiosqlite


_INIT_SQL = """
CREATE TABLE IF NOT EXISTS platform_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    must_change_password INTEGER NOT NULL DEFAULT 1,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    last_login_at REAL
);
CREATE TABLE IF NOT EXISTS platform_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_token_hash TEXT NOT NULL UNIQUE,
    expires_at REAL NOT NULL,
    created_at REAL NOT NULL,
    last_seen_at REAL NOT NULL,
    revoked_at REAL,
    FOREIGN KEY (user_id) REFERENCES platform_users(id)
);
CREATE TABLE IF NOT EXISTS saved_hosts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_user_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    provider_type TEXT NOT NULL,
    host TEXT,
    port INTEGER,
    username TEXT,
    auth_type TEXT,
    sudo_enabled INTEGER NOT NULL DEFAULT 0,
    host_fingerprint TEXT,
    agent_url TEXT,
    credential_ref TEXT,
    last_connected_at REAL NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    FOREIGN KEY (owner_user_id) REFERENCES platform_users(id)
);
"""


class PlatformIdentityStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def init(self):
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path, timeout=30.0)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_INIT_SQL)
        await self._db.commit()

    async def close(self):
        if self._db:
            await self._db.close()

    async def get_user_by_username(self, username: str):
        row = await (await self._db.execute(
            "SELECT * FROM platform_users WHERE username = ?",
            (username,),
        )).fetchone()
        return dict(row) if row else None

    async def create_user(self, username: str, password_hash: str, role: str, must_change_password: bool):
        now = time.time()
        cursor = await self._db.execute(
            """INSERT INTO platform_users
               (username, password_hash, role, must_change_password, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, 1, ?, ?)""",
            (username, password_hash, role, int(must_change_password), now, now),
        )
        await self._db.commit()
        return await self.get_user_by_id(cursor.lastrowid)

    async def get_user_by_id(self, user_id: int):
        row = await (await self._db.execute(
            "SELECT * FROM platform_users WHERE id = ?",
            (user_id,),
        )).fetchone()
        return dict(row) if row else None

    async def update_password(self, user_id: int, password_hash: str, must_change_password: bool):
        now = time.time()
        await self._db.execute(
            """UPDATE platform_users
               SET password_hash = ?, must_change_password = ?, updated_at = ?
               WHERE id = ?""",
            (password_hash, int(must_change_password), now, user_id),
        )
        await self._db.commit()

    async def create_session(self, user_id: int, token_hash: str, expires_at: float):
        now = time.time()
        await self._db.execute(
            """INSERT INTO platform_sessions
               (user_id, session_token_hash, expires_at, created_at, last_seen_at)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, token_hash, expires_at, now, now),
        )
        await self._db.execute(
            "UPDATE platform_users SET last_login_at = ? WHERE id = ?",
            (now, user_id),
        )
        await self._db.commit()

    async def get_session_by_token(self, raw_token: str):
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        row = await (await self._db.execute(
            """SELECT s.*, u.username, u.role, u.must_change_password, u.is_active
               FROM platform_sessions s
               JOIN platform_users u ON u.id = s.user_id
               WHERE s.session_token_hash = ? AND s.revoked_at IS NULL""",
            (token_hash,),
        )).fetchone()
        return dict(row) if row else None

    async def revoke_session(self, raw_token: str):
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        await self._db.execute(
            "UPDATE platform_sessions SET revoked_at = ? WHERE session_token_hash = ? AND revoked_at IS NULL",
            (time.time(), token_hash),
        )
        await self._db.commit()

    async def list_users(self):
        rows = await (await self._db.execute(
            """SELECT id, username, role, must_change_password, is_active, created_at, updated_at, last_login_at
               FROM platform_users
               ORDER BY username ASC"""
        )).fetchall()
        return [dict(row) for row in rows]

    async def upsert_saved_host(
        self,
        owner_user_id: int,
        label: str,
        provider_type: str,
        host: str | None,
        port: int | None,
        username: str | None,
        auth_type: str | None,
        sudo_enabled: bool,
        host_fingerprint: str | None,
        agent_url: str | None,
        credential_ref: str | None,
    ):
        now = time.time()
        row = await (await self._db.execute(
            """SELECT id FROM saved_hosts
               WHERE owner_user_id = ? AND provider_type = ?
                 AND COALESCE(host, '') = COALESCE(?, '')
                 AND COALESCE(port, 0) = COALESCE(?, 0)
                 AND COALESCE(username, '') = COALESCE(?, '')
                 AND COALESCE(agent_url, '') = COALESCE(?, '')""",
            (owner_user_id, provider_type, host, port, username, agent_url),
        )).fetchone()
        if row:
            await self._db.execute(
                """UPDATE saved_hosts
                   SET label = ?, auth_type = ?, sudo_enabled = ?, host_fingerprint = ?,
                       credential_ref = ?, last_connected_at = ?, updated_at = ?
                   WHERE id = ?""",
                (
                    label,
                    auth_type,
                    int(sudo_enabled),
                    host_fingerprint,
                    credential_ref,
                    now,
                    now,
                    row["id"],
                ),
            )
            await self._db.commit()
            return await self.get_saved_host(row["id"])
        cursor = await self._db.execute(
            """INSERT INTO saved_hosts
               (owner_user_id, label, provider_type, host, port, username, auth_type, sudo_enabled,
                host_fingerprint, agent_url, credential_ref, last_connected_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                owner_user_id,
                label,
                provider_type,
                host,
                port,
                username,
                auth_type,
                int(sudo_enabled),
                host_fingerprint,
                agent_url,
                credential_ref,
                now,
                now,
                now,
            ),
        )
        await self._db.commit()
        return await self.get_saved_host(cursor.lastrowid)

    async def list_saved_hosts(self, owner_user_id: int | None = None):
        sql = """SELECT h.*, u.username AS owner_username
                 FROM saved_hosts h
                 JOIN platform_users u ON u.id = h.owner_user_id"""
        params = ()
        if owner_user_id is not None:
            sql += " WHERE h.owner_user_id = ?"
            params = (owner_user_id,)
        sql += " ORDER BY h.updated_at DESC"
        rows = await (await self._db.execute(sql, params)).fetchall()
        return [dict(row) for row in rows]

    async def get_saved_host(self, host_id: int):
        row = await (await self._db.execute(
            """SELECT h.*, u.username AS owner_username
               FROM saved_hosts h
               JOIN platform_users u ON u.id = h.owner_user_id
               WHERE h.id = ?""",
            (host_id,),
        )).fetchone()
        return dict(row) if row else None

    async def delete_saved_host(self, host_id: int):
        await self._db.execute("DELETE FROM saved_hosts WHERE id = ?", (host_id,))
        await self._db.commit()
```

Create `backend/app/services/platform_auth_service.py`:

```python
from __future__ import annotations

import hashlib
import secrets
import time

from app.services.password_hasher import hash_password, verify_password


DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_ROLE = "admin"
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60


class PlatformAuthService:
    def __init__(self, store):
        self.store = store

    async def ensure_default_admin(self):
        current = await self.store.get_user_by_username(DEFAULT_ADMIN_USERNAME)
        if current:
            return None
        generated_password = secrets.token_urlsafe(12)
        user = await self.store.create_user(
            username=DEFAULT_ADMIN_USERNAME,
            password_hash=hash_password(generated_password),
            role=DEFAULT_ADMIN_ROLE,
            must_change_password=True,
        )
        return {"username": user["username"], "generated_password": generated_password}

    async def login(self, username: str, password: str):
        user = await self.store.get_user_by_username(username)
        if not user or not user["is_active"]:
            raise ValueError("用户名或密码错误")
        if not verify_password(password, user["password_hash"]):
            raise ValueError("用户名或密码错误")
        token = secrets.token_urlsafe(32)
        await self.store.create_session(
            user_id=user["id"],
            token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            expires_at=time.time() + SESSION_TTL_SECONDS,
        )
        fresh_user = await self.store.get_user_by_id(user["id"])
        return {"token": token, "user": _public_user(fresh_user)}

    async def resolve_session(self, token: str):
        if not token:
            return None
        session = await self.store.get_session_by_token(token)
        if not session:
            return None
        if session["revoked_at"] is not None or session["expires_at"] <= time.time():
            return None
        if not session["is_active"]:
            return None
        return {
            "id": session["user_id"],
            "username": session["username"],
            "role": session["role"],
            "must_change_password": bool(session["must_change_password"]),
        }

    async def change_password(self, user_id: int, current_password: str, new_password: str):
        user = await self.store.get_user_by_id(user_id)
        if not user or not verify_password(current_password, user["password_hash"]):
            raise ValueError("当前密码错误")
        await self.store.update_password(user_id, hash_password(new_password), False)

    async def logout(self, token: str):
        await self.store.revoke_session(token)

    async def create_user(self, username: str, password: str, role: str, must_change_password: bool):
        existing = await self.store.get_user_by_username(username)
        if existing:
            raise ValueError("用户名已存在")
        user = await self.store.create_user(
            username=username,
            password_hash=hash_password(password),
            role=role,
            must_change_password=must_change_password,
        )
        return _public_user(user)

    async def reset_password(self, user_id: int, password: str, must_change_password: bool):
        user = await self.store.get_user_by_id(user_id)
        if not user:
            raise ValueError("用户不存在")
        await self.store.update_password(user_id, hash_password(password), must_change_password)


def _public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "must_change_password": bool(user["must_change_password"]),
    }
```

Modify `backend/app/services/credential_store.py`:

```python
class CredentialStore:
    def __init__(self, config_path: str, cipher):
        self.config_path = config_path
        self.cipher = cipher
        self._data = self._load()

    def _require_cipher(self):
        if self.cipher is None:
            raise ValueError("平台未配置主密钥 GPU_GOV_MASTER_KEY，无法保存或读取 SSH 凭据")

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
        stored = self._data.get(str(credential_id), {})
        return {
            key: self.cipher.decrypt(value)
            for key, value in stored.items()
        }

    def delete(self, credential_id: str) -> None:
        self._data.pop(str(credential_id), None)
        self._persist()
```

Modify `backend/app/main.py` startup and shutdown wiring:

```python
from app.services.credential_cipher import CredentialCipher
from app.services.platform_auth_service import PlatformAuthService
from app.services.platform_identity_store import PlatformIdentityStore
```

and inside `lifespan()` setup:

```python
    identity_db_path = os.path.join(runtime_dir, "platform_identity.db")
    master_key = os.getenv("GPU_GOV_MASTER_KEY", "").strip()
    cipher = CredentialCipher(master_key) if master_key else None

    app_state.identity = PlatformIdentityStore(identity_db_path)
    await app_state.identity.init()
    app_state.platform_auth = PlatformAuthService(app_state.identity)
    bootstrap_notice = await app_state.platform_auth.ensure_default_admin()
    if bootstrap_notice:
        logger.warning(
            "默认管理员已创建: username=%s temporary_password=%s",
            bootstrap_notice["username"],
            bootstrap_notice["generated_password"],
        )

    app_state.credentials = CredentialStore(credential_config_path, cipher)
```

and shutdown:

```python
    await app_state.identity.close()
```

- [ ] **Step 4: Run the new backend tests and verify they pass**

Run:

```bash
timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m unittest tests.test_platform_identity_flow tests.test_encrypted_credential_store tests.test_credential_store -v"
```

Expected:

- PASS for default-admin bootstrap
- PASS for login/logout/change-password flow
- PASS for encrypted credential persistence with no plaintext in JSON

- [ ] **Step 5: Commit the backend identity primitives**

```bash
git add backend/requirements.txt backend/app/services/password_hasher.py backend/app/services/credential_cipher.py backend/app/services/platform_identity_store.py backend/app/services/platform_auth_service.py backend/app/services/credential_store.py backend/app/main.py tests/test_platform_identity_flow.py tests/test_encrypted_credential_store.py tests/test_credential_store.py
git commit -m "feat: add platform identity and encrypted credentials"
```

---

### Task 3: Define Red Tests For Saved Hosts, Session-First Middleware, And Import Reuse

**Files:**
- Create: `tests/test_saved_host_service.py`
- Modify: `tests/test_ssh_import_flow.py`
- Modify: `backend/tests/test_auth.py`
- Test: `tests/test_saved_host_service.py`
- Test: `tests/test_ssh_import_flow.py`
- Test: `backend/tests/test_auth.py`

- [ ] **Step 1: Add failing saved-host service tests**

Create `tests/test_saved_host_service.py`:

```python
import os
import sys
import tempfile
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.credential_cipher import CredentialCipher  # noqa: E402
from app.services.credential_store import CredentialStore  # noqa: E402
from app.services.platform_auth_service import PlatformAuthService  # noqa: E402
from app.services.platform_identity_store import PlatformIdentityStore  # noqa: E402
from app.services.saved_host_service import SavedHostService  # noqa: E402
from app.services.runtime_provider import RuntimeTarget  # noqa: E402


class SavedHostServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tempdir.name, "platform.db")
        self.secret_path = os.path.join(self.tempdir.name, "credentials.json")
        self.identity = PlatformIdentityStore(self.db_path)
        await self.identity.init()
        self.auth = PlatformAuthService(self.identity)
        notice = await self.auth.ensure_default_admin()
        self.admin_login = await self.auth.login("admin", notice["generated_password"])
        self.cipher = CredentialCipher("unit-test-master-key")
        self.credentials = CredentialStore(self.secret_path, self.cipher)
        self.service = SavedHostService(self.identity, self.credentials)

        self.member = await self.identity.create_user(
            username="alice",
            password_hash="unused-for-this-test",
            role="member",
            must_change_password=False,
        )

    async def asyncTearDown(self):
        await self.identity.close()
        self.tempdir.cleanup()

    async def test_member_only_lists_owned_hosts(self):
        target = RuntimeTarget(
            provider_type="ssh_linux",
            label="训练机 A",
            host="10.0.0.8",
            port=22,
            username="alice",
            auth_type="password",
        )
        credential_id = self.credentials.save({"password": "secret"})

        await self.service.upsert_host(self.member, target, credential_id)
        hosts = await self.service.list_hosts(self.member)

        self.assertEqual(len(hosts), 1)
        self.assertEqual(hosts[0]["owner_user_id"], self.member["id"])

    async def test_admin_can_list_all_hosts(self):
        target = RuntimeTarget(
            provider_type="ssh_linux",
            label="训练机 A",
            host="10.0.0.8",
            port=22,
            username="alice",
            auth_type="password",
        )
        credential_id = self.credentials.save({"password": "secret"})
        await self.service.upsert_host(self.member, target, credential_id)

        hosts = await self.service.list_hosts({
            "id": self.admin_login["user"]["id"],
            "username": "admin",
            "role": "admin",
            "must_change_password": False,
        }, scope="all")

        self.assertEqual(len(hosts), 1)
        self.assertEqual(hosts[0]["owner_username"], "alice")

    async def test_resolve_host_returns_target_and_credentials(self):
        target = RuntimeTarget(
            provider_type="ssh_linux",
            label="训练机 A",
            host="10.0.0.8",
            port=22,
            username="alice",
            auth_type="password",
        )
        credential_id = self.credentials.save({"password": "secret"})
        record = await self.service.upsert_host(self.member, target, credential_id)

        resolved_target, credentials, owner = await self.service.resolve_for_import(self.member, record["id"])

        self.assertEqual(resolved_target.host, "10.0.0.8")
        self.assertEqual(credentials["password"], "secret")
        self.assertEqual(owner["username"], "alice")

    async def test_member_cannot_access_other_users_host_record(self):
        other = await self.identity.create_user(
            username="bob",
            password_hash="unused-for-this-test",
            role="member",
            must_change_password=False,
        )
        target = RuntimeTarget(
            provider_type="ssh_linux",
            label="训练机 B",
            host="10.0.0.9",
            port=22,
            username="bob",
            auth_type="password",
        )
        credential_id = self.credentials.save({"password": "secret"})
        record = await self.service.upsert_host(other, target, credential_id)

        with self.assertRaises(PermissionError):
            await self.service.resolve_for_import(self.member, record["id"])
```

- [ ] **Step 2: Extend import-flow and middleware tests**

Append to `tests/test_ssh_import_flow.py`:

```python
    async def test_scan_import_context_supports_saved_host_id(self):
        saved_hosts = types.SimpleNamespace(
            resolve_for_import=mock.AsyncMock(return_value=(
                RuntimeTarget(
                    provider_type="ssh_linux",
                    label="训练机 A",
                    host="10.0.0.8",
                    port=22,
                    username="gpuops",
                    auth_type="password",
                ),
                {"password": "secret"},
                {"id": 2, "username": "alice", "role": "member", "must_change_password": False},
            )),
        )
        fake_app_state = types.SimpleNamespace(
            connection=FakeConnection(),
            runtime=FakeRuntime(),
            credentials=FakeCredentials(),
            import_context=FakeImportContext(),
            saved_hosts=saved_hosts,
        )
        request = ImportScanRequest(saved_host_id=8)

        with mock.patch("app.main.app_state", fake_app_state):
            with mock.patch("app.api.system.require_authenticated_user", return_value={"id": 2, "username": "alice", "role": "member", "must_change_password": False}):
                response = await scan_import_context(mock.Mock(), request)

        self.assertTrue(response["success"])
        saved_hosts.resolve_for_import.assert_awaited_once()
```

Append to `backend/tests/test_auth.py`:

```python
from app.middleware.auth import PASSWORD_CHANGE_ALLOWED_PREFIXES, SESSION_PUBLIC_PREFIXES

    def test_session_public_prefixes_include_login(self):
        assert "/api/auth/login" in SESSION_PUBLIC_PREFIXES

    def test_password_change_only_paths_include_change_password(self):
        assert "/api/auth/change-password" in PASSWORD_CHANGE_ALLOWED_PREFIXES
```

- [ ] **Step 3: Run the red tests and verify they fail**

Run:

```bash
timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m unittest tests.test_saved_host_service tests.test_ssh_import_flow -v"
timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m pytest backend/tests/test_auth.py -v"
```

Expected:

- FAIL because `SavedHostService` and `saved_host_id` flow do not exist yet
- FAIL because middleware constants for session public paths and forced-password-change routes do not exist yet

- [ ] **Step 4: Commit the red tests**

```bash
git add tests/test_saved_host_service.py tests/test_ssh_import_flow.py backend/tests/test_auth.py
git commit -m "test: define saved host auth and import reuse"
```

---

### Task 4: Implement Saved Hosts, Session-First Middleware, Auth APIs, And Import Reuse

**Files:**
- Create: `backend/app/services/saved_host_service.py`
- Create: `backend/app/api/auth_access.py`
- Create: `backend/app/api/auth.py`
- Create: `backend/app/api/admin_users.py`
- Create: `backend/app/api/hosts.py`
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/middleware/auth.py`
- Modify: `backend/app/api/system.py`
- Modify: `backend/app/main.py`
- Modify: `tests/test_saved_host_service.py`
- Modify: `tests/test_ssh_import_flow.py`
- Modify: `backend/tests/test_auth.py`
- Test: `tests/test_saved_host_service.py`
- Test: `tests/test_ssh_import_flow.py`
- Test: `backend/tests/test_auth.py`

- [ ] **Step 1: Add schemas and saved-host service**

Extend `backend/app/models/schemas.py` with:

```python
class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=500)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=500)
    new_password: str = Field(min_length=8, max_length=500)


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=500)
    role: str = Field(default="member", pattern=r"^(admin|member)$")
    must_change_password: bool = True


class ResetPasswordRequest(BaseModel):
    password: str = Field(min_length=8, max_length=500)
    must_change_password: bool = True
```

and extend `ProviderBackedImportRequest`:

```python
    saved_host_id: Optional[int] = Field(default=None, ge=1)
```

Create `backend/app/services/saved_host_service.py`:

```python
from __future__ import annotations

from app.services.runtime_provider import RuntimeTarget


class SavedHostService:
    def __init__(self, identity_store, credential_store):
        self.identity_store = identity_store
        self.credential_store = credential_store

    async def list_hosts(self, actor: dict, scope: str = "mine"):
        owner_id = None if actor["role"] == "admin" and scope == "all" else actor["id"]
        return await self.identity_store.list_saved_hosts(owner_user_id=owner_id)

    async def upsert_host(self, owner: dict, target: RuntimeTarget, credential_id: str | None):
        return await self.identity_store.upsert_saved_host(
            owner_user_id=owner["id"],
            label=target.label,
            provider_type=target.provider_type,
            host=target.host,
            port=target.port,
            username=target.username,
            auth_type=target.auth_type,
            sudo_enabled=bool(target.sudo_enabled),
            host_fingerprint=target.host_fingerprint,
            agent_url=target.agent_url,
            credential_ref=credential_id,
        )

    async def resolve_for_import(self, actor: dict, host_id: int):
        record = await self.identity_store.get_saved_host(host_id)
        if not record:
            raise ValueError("指定主机不存在")
        if actor["role"] != "admin" and record["owner_user_id"] != actor["id"]:
            raise PermissionError("无权访问该主机记录")
        target = RuntimeTarget(
            provider_type=record["provider_type"],
            label=record["label"],
            host=record["host"],
            port=record["port"],
            username=record["username"],
            auth_type=record["auth_type"],
            sudo_enabled=bool(record["sudo_enabled"]),
            host_fingerprint=record["host_fingerprint"],
            agent_url=record["agent_url"],
            credential_id=record["credential_ref"],
        )
        credentials = self.credential_store.read(record["credential_ref"]) if record["credential_ref"] else {}
        owner = await self.identity_store.get_user_by_id(record["owner_user_id"])
        return target, credentials, owner

    async def delete_host(self, actor: dict, host_id: int):
        record = await self.identity_store.get_saved_host(host_id)
        if not record:
            raise ValueError("指定主机不存在")
        if actor["role"] != "admin" and record["owner_user_id"] != actor["id"]:
            raise PermissionError("无权删除该主机记录")
        if record["credential_ref"]:
            self.credential_store.delete(record["credential_ref"])
        await self.identity_store.delete_saved_host(host_id)
```

- [ ] **Step 2: Add auth-access helpers and API routers**

Create `backend/app/api/auth_access.py`:

```python
from fastapi import HTTPException, Request


def require_authenticated_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录平台")
    return user


def require_admin_user(request: Request) -> dict:
    user = require_authenticated_user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="此操作需要管理员权限")
    return user
```

Create `backend/app/api/auth.py`:

```python
from fastapi import APIRouter, HTTPException, Request

from app.api.auth_access import require_authenticated_user
from app.models.schemas import ChangePasswordRequest, LoginRequest


router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/login")
async def login(req: LoginRequest):
    from app.main import app_state

    try:
        result = await app_state.platform_auth.login(req.username, req.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {"success": True, **result}


@router.get("/me")
async def me(request: Request):
    return {"user": require_authenticated_user(request)}


@router.post("/logout")
async def logout(request: Request):
    from app.main import app_state

    token = getattr(request.state, "auth_token", "")
    await app_state.platform_auth.logout(token)
    return {"success": True}


@router.post("/change-password")
async def change_password(request: Request, req: ChangePasswordRequest):
    from app.main import app_state

    user = require_authenticated_user(request)
    try:
        await app_state.platform_auth.change_password(
            user_id=user["id"],
            current_password=req.current_password,
            new_password=req.new_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True}
```

Create `backend/app/api/admin_users.py` and `backend/app/api/hosts.py` with the exact handlers:

```python
from fastapi import APIRouter, HTTPException, Request

from app.api.auth_access import require_admin_user
from app.models.schemas import CreateUserRequest, ResetPasswordRequest


router = APIRouter(prefix="/api/admin", tags=["Admin Users"])


@router.get("/users")
async def list_users(request: Request):
    from app.main import app_state
    require_admin_user(request)
    return {"users": await app_state.identity.list_users()}
```

```python
@router.post("/users")
async def create_user(request: Request, req: CreateUserRequest):
    from app.main import app_state

    require_admin_user(request)
    try:
        user = await app_state.platform_auth.create_user(
            username=req.username,
            password=req.password,
            role=req.role,
            must_change_password=req.must_change_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "user": user}

@router.post("/users/{user_id}/reset-password")
async def reset_password(request: Request, user_id: int, req: ResetPasswordRequest):
    from app.main import app_state

    require_admin_user(request)
    try:
        await app_state.platform_auth.reset_password(
            user_id=user_id,
            password=req.password,
            must_change_password=req.must_change_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True}
```

```python
from fastapi import APIRouter, HTTPException, Request

from app.api.auth_access import require_authenticated_user


router = APIRouter(prefix="/api", tags=["Saved Hosts"])


@router.get("/hosts")
async def list_hosts(request: Request, scope: str = "mine"):
    from app.main import app_state
    user = require_authenticated_user(request)
    return {"hosts": await app_state.saved_hosts.list_hosts(user, scope=scope)}

@router.delete("/hosts/{host_id}")
async def delete_host(request: Request, host_id: int):
    from app.main import app_state

    user = require_authenticated_user(request)
    try:
        await app_state.saved_hosts.delete_host(user, host_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True}
```

- [ ] **Step 3: Upgrade middleware, WebSocket, and import-context reuse**

Modify `backend/app/middleware/auth.py`:

```python
SESSION_PUBLIC_PREFIXES = (
    "/api/health",
    "/api/auth/login",
    "/docs",
    "/openapi.json",
    "/redoc",
)

PASSWORD_CHANGE_ALLOWED_PREFIXES = (
    "/api/auth/me",
    "/api/auth/logout",
    "/api/auth/change-password",
    "/api/health",
)
```

and delete the old `TRUSTED_LOCAL_HOSTS` local-admin shortcut plus the anonymous-GET fallback, then replace the dispatch core with:

```python
        token = _extract_token(request)
        session_user = None
        if token:
            from app.main import app_state
            session_user = await app_state.platform_auth.resolve_session(token)

        role = _resolve_role(token)
        if session_user is not None:
            request.state.user = session_user
            request.state.role = session_user["role"]
            request.state.auth_token = token
            if session_user["must_change_password"]:
                if not any(path.startswith(prefix) for prefix in PASSWORD_CHANGE_ALLOWED_PREFIXES):
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "首次登录后必须先修改密码", "code": "PASSWORD_CHANGE_REQUIRED"},
                    )
            return await call_next(request)

        if any(path.startswith(prefix) for prefix in SESSION_PUBLIC_PREFIXES):
            return await call_next(request)

        if role is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "请先登录平台", "code": "UNAUTHORIZED"},
            )
```

Modify `backend/app/api/system.py` to accept `Request` and `saved_host_id`:

```python
from fastapi import APIRouter, HTTPException, Request
from app.api.auth_access import require_authenticated_user
```

Add a shared resolver:

```python
async def _resolve_import_target(request: Request, req: ImportScanRequest | ImportCommitRequest):
    from app.main import app_state

    if req.saved_host_id:
        user = require_authenticated_user(request)
        try:
            return await app_state.saved_hosts.resolve_for_import(user, req.saved_host_id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    target = app_state.connection.normalize_payload(req.provider_payload())
    return target, req.credential_payload(), require_authenticated_user(request)
```

Use it in `scan_import_context()` and `commit_import_context()`:

```python
    target, credentials, owner = await _resolve_import_target(request, req)
    probe = await app_state.runtime.probe_target(target, credentials)
```

and after successful import:

```python
    if target.provider_type == "ssh_linux" or target.provider_type.startswith("http_"):
        await app_state.saved_hosts.upsert_host(owner, saved_target, credential_id)
```

Modify `backend/app/main.py` router and WebSocket registration:

```python
from app.api.auth import router as auth_router
from app.api.admin_users import router as admin_users_router
from app.api.hosts import router as hosts_router
from app.services.saved_host_service import SavedHostService
```

```python
app_state.saved_hosts = SavedHostService(app_state.identity, app_state.credentials)
app.include_router(auth_router)
app.include_router(admin_users_router)
app.include_router(hosts_router)
```

and:

```python
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    token = ws.query_params.get("token")
    user = await app_state.platform_auth.resolve_session(token)
    if not user:
        await ws.close(code=4401, reason="UNAUTHORIZED")
        return
    if user["must_change_password"]:
        await ws.close(code=4403, reason="PASSWORD_CHANGE_REQUIRED")
        return
    await ws_manager.connect(ws)
```

- [ ] **Step 4: Run backend auth and import reuse tests**

Run:

```bash
timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m unittest tests.test_saved_host_service tests.test_ssh_import_flow -v"
timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m pytest backend/tests/test_auth.py -v"
```

Expected:

- PASS for owner/admin host visibility and delete rules
- PASS for `saved_host_id` scan/import reuse
- PASS for session-first middleware constants and forced-password-change restrictions

- [ ] **Step 5: Commit the backend auth and saved-host wiring**

```bash
git add backend/app/services/saved_host_service.py backend/app/api/auth_access.py backend/app/api/auth.py backend/app/api/admin_users.py backend/app/api/hosts.py backend/app/models/schemas.py backend/app/middleware/auth.py backend/app/api/system.py backend/app/main.py tests/test_saved_host_service.py tests/test_ssh_import_flow.py backend/tests/test_auth.py
git commit -m "feat: add session auth and saved host import reuse"
```

---

### Task 5: Define Red Frontend Tests For Auth Routing And Shell Separation

**Files:**
- Create: `frontend/src/stores/auth.test.js`
- Create: `frontend/src/lib/routeAccess.test.js`
- Modify: `tests/test_frontend_ui_structure.py`
- Test: `frontend/src/stores/auth.test.js`
- Test: `frontend/src/lib/routeAccess.test.js`
- Test: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Add failing auth-store and route-access tests**

Create `frontend/src/stores/auth.test.js`:

```javascript
import test from 'node:test'
import assert from 'node:assert/strict'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from './auth.js'

function installStorage() {
  const data = new Map()
  globalThis.localStorage = {
    getItem(key) { return data.has(key) ? data.get(key) : null },
    setItem(key, value) { data.set(key, String(value)) },
    removeItem(key) { data.delete(key) },
  }
}

test('auth store persists and clears session token', () => {
  installStorage()
  setActivePinia(createPinia())
  const store = useAuthStore()

  store.setSession({
    token: 'session-token',
    user: { id: 1, username: 'admin', role: 'admin', must_change_password: true },
  })

  assert.equal(store.isAuthenticated, true)
  assert.equal(store.mustChangePassword, true)

  store.clearSession()
  assert.equal(store.isAuthenticated, false)
})
```

Create `frontend/src/lib/routeAccess.test.js`:

```javascript
import test from 'node:test'
import assert from 'node:assert/strict'
import { resolveRouteRedirect, usesMinimalShellRoute } from './routeAccess.js'

test('anonymous user is redirected to /login', () => {
  assert.equal(
    resolveRouteRedirect({
      path: '/',
      isAuthenticated: false,
      mustChangePassword: false,
      workspaceReady: false,
    }),
    '/login',
  )
})

test('must-change-password user is redirected away from import', () => {
  assert.equal(
    resolveRouteRedirect({
      path: '/import',
      isAuthenticated: true,
      mustChangePassword: true,
      workspaceReady: false,
    }),
    '/change-password',
  )
})

test('login and change-password use minimal shell', () => {
  assert.equal(usesMinimalShellRoute('/login'), true)
  assert.equal(usesMinimalShellRoute('/change-password'), true)
})
```

- [ ] **Step 2: Add failing frontend structure assertions**

Append to `tests/test_frontend_ui_structure.py`:

```python
    def test_router_includes_login_and_change_password_routes(self):
        text = (ROOT / "frontend/src/main.js").read_text(encoding="utf-8")
        self.assertIn("path: '/login'", text)
        self.assertIn("path: '/change-password'", text)

    def test_app_shell_supports_auth_only_minimal_layout(self):
        text = (ROOT / "frontend/src/App.vue").read_text(encoding="utf-8")
        self.assertIn("usesMinimalShellRoute", text)
        self.assertIn("LoginView", (ROOT / "frontend/src/main.js").read_text(encoding="utf-8"))

    def test_import_tabs_include_saved_hosts_stage(self):
        text = (ROOT / "frontend/src/lib/importWorkbench.js").read_text(encoding="utf-8")
        self.assertIn("已保存主机", text)
```

- [ ] **Step 3: Run the red frontend tests**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm test -- src/stores/auth.test.js src/lib/routeAccess.test.js"
timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m unittest tests.test_frontend_ui_structure -v"
```

Expected:

- FAIL because `auth.js` and `routeAccess.js` do not exist yet
- FAIL because router and app shell do not yet define login/change-password routes

- [ ] **Step 4: Commit the red frontend tests**

```bash
git add frontend/src/stores/auth.test.js frontend/src/lib/routeAccess.test.js tests/test_frontend_ui_structure.py
git commit -m "test: define frontend auth routing and shell gating"
```

---

### Task 6: Implement Frontend Auth Store, Routes, API Wiring, And Session-Aware Shell

**Files:**
- Create: `frontend/src/lib/authSession.js`
- Create: `frontend/src/lib/routeAccess.js`
- Create: `frontend/src/stores/auth.js`
- Create: `frontend/src/views/LoginView.vue`
- Create: `frontend/src/views/ChangePasswordView.vue`
- Modify: `frontend/src/services/api.js`
- Modify: `frontend/src/composables/useWebSocket.js`
- Modify: `frontend/src/stores/app.js`
- Modify: `frontend/src/main.js`
- Modify: `frontend/src/App.vue`
- Test: `frontend/src/stores/auth.test.js`
- Test: `frontend/src/lib/routeAccess.test.js`
- Test: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Add session-token helpers and auth store**

Create `frontend/src/lib/authSession.js`:

```javascript
export const AUTH_SESSION_KEY = 'gpu_gov_session_token'

export function readSessionToken() {
  return globalThis.localStorage?.getItem(AUTH_SESSION_KEY) || ''
}

export function writeSessionToken(token) {
  if (!token) return
  globalThis.localStorage?.setItem(AUTH_SESSION_KEY, token)
}

export function clearSessionToken() {
  globalThis.localStorage?.removeItem(AUTH_SESSION_KEY)
}
```

Create `frontend/src/stores/auth.js`:

```javascript
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { clearSessionToken, readSessionToken, writeSessionToken } from '../lib/authSession.js'
import { changePassword, getCurrentUser, login, logout } from '../services/api.js'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const hydrated = ref(false)
  const busy = ref(false)

  const token = computed(() => readSessionToken())
  const isAuthenticated = computed(() => Boolean(user.value && token.value))
  const mustChangePassword = computed(() => Boolean(user.value?.must_change_password))

  function setSession(payload) {
    writeSessionToken(payload?.token || '')
    user.value = payload?.user || null
    hydrated.value = true
  }

  function clearSession() {
    clearSessionToken()
    user.value = null
    hydrated.value = true
  }

  async function restoreSession() {
    if (!token.value) {
      hydrated.value = true
      user.value = null
      return
    }
    try {
      const { data } = await getCurrentUser()
      user.value = data.user
    } catch {
      clearSession()
    } finally {
      hydrated.value = true
    }
  }

  async function signIn(username, password) {
    busy.value = true
    try {
      const { data } = await login({ username, password })
      setSession({ token: data.token, user: data.user })
      return data.user
    } finally {
      busy.value = false
    }
  }

  async function signOut() {
    try {
      if (token.value) await logout()
    } finally {
      clearSession()
    }
  }

  async function updatePassword(payload) {
    await changePassword(payload)
    await restoreSession()
  }

  return {
    user,
    hydrated,
    busy,
    token,
    isAuthenticated,
    mustChangePassword,
    setSession,
    clearSession,
    restoreSession,
    signIn,
    signOut,
    updatePassword,
  }
})
```

- [ ] **Step 2: Add pure route-access helpers and standalone auth views**

Create `frontend/src/lib/routeAccess.js`:

```javascript
const MINIMAL_SHELL_PATHS = new Set(['/login', '/change-password', '/import'])

export function usesMinimalShellRoute(path = '') {
  return MINIMAL_SHELL_PATHS.has(path)
}

export function resolveRouteRedirect({
  path = '/',
  isAuthenticated = false,
  mustChangePassword = false,
  workspaceReady = false,
}) {
  if (!isAuthenticated) {
    return path === '/login' ? null : '/login'
  }
  if (mustChangePassword) {
    return path === '/change-password' ? null : '/change-password'
  }
  if (!workspaceReady) {
    return path === '/import' ? null : '/import'
  }
  if (path === '/login' || path === '/change-password' || path === '/import') {
    return '/'
  }
  return null
}
```

Create `frontend/src/views/LoginView.vue`:

```vue
<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const router = useRouter()
const auth = useAuthStore()
const form = reactive({ username: '', password: '' })
const errorText = ref('')

async function handleSubmit() {
  errorText.value = ''
  try {
    const user = await auth.signIn(form.username, form.password)
    router.replace(user.must_change_password ? '/change-password' : '/import')
  } catch (error) {
    errorText.value = error?.response?.data?.detail || error?.message || '登录失败'
  }
}
</script>
```

Create `frontend/src/views/ChangePasswordView.vue`:

```vue
<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const router = useRouter()
const auth = useAuthStore()
const form = reactive({ current_password: '', new_password: '' })
const errorText = ref('')

async function handleSubmit() {
  errorText.value = ''
  try {
    await auth.updatePassword(form)
    router.replace('/import')
  } catch (error) {
    errorText.value = error?.response?.data?.detail || error?.message || '修改密码失败'
  }
}
</script>
```

- [ ] **Step 3: Wire API, router guards, WebSocket token, app reset, and shell layout**

Modify `frontend/src/services/api.js`:

```javascript
import { readSessionToken } from '../lib/authSession.js'
```

replace request interceptor token lookup with:

```javascript
  const token = readSessionToken()
```

and add:

```javascript
export const login = (payload) => api.post('/auth/login', payload)
export const logout = () => api.post('/auth/logout')
export const getCurrentUser = () => api.get('/auth/me')
export const changePassword = (payload) => api.post('/auth/change-password', payload)
export const getUsers = () => api.get('/admin/users')
export const createUser = (payload) => api.post('/admin/users', payload)
export const resetUserPassword = (id, payload) => api.post(`/admin/users/${id}/reset-password`, payload)
export const getSavedHosts = (scope = 'mine') => api.get('/hosts', { params: { scope } })
export const deleteSavedHost = (id) => api.delete(`/hosts/${id}`)
```

Modify `frontend/src/composables/useWebSocket.js`:

```javascript
import { readSessionToken } from '../lib/authSession.js'
```

and:

```javascript
function buildWebSocketUrl() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const token = encodeURIComponent(readSessionToken())
  return `${protocol}//${location.host}/ws?token=${token}`
}

function connect() {
  const token = readSessionToken()
  if (!token) {
    notifyConnectionChange(false)
    return
  }
  manualDisconnect = false
  socket = new WebSocket(buildWebSocketUrl())
  // keep the rest of the existing onopen/onmessage/onclose/onerror logic
}
```

Modify `frontend/src/stores/app.js`:

```javascript
  function resetRuntimeState() {
    gpus.value = []
    system.value = null
    processes.value = []
    alerts.value = []
    workspaceReady.value = false
    importContext.value = null
    runtimeStatus.value = normalizeRuntimeStatus()
  }
```

and return `resetRuntimeState`.

Modify `frontend/src/main.js`:

```javascript
import { useAuthStore } from './stores/auth.js'
import { resolveRouteRedirect } from './lib/routeAccess.js'
import { useAppStore } from './stores/app.js'
const loadLoginView = () => import('./views/LoginView.vue')
const loadChangePasswordView = () => import('./views/ChangePasswordView.vue')
```

add routes:

```javascript
  { path: '/login', name: 'Login', component: loadLoginView },
  { path: '/change-password', name: 'ChangePassword', component: loadChangePasswordView },
```

and install the guard:

```javascript
const pinia = createPinia()
const auth = useAuthStore(pinia)

router.beforeEach(async (to) => {
  if (!auth.hydrated) {
    await auth.restoreSession()
  }
  const redirect = resolveRouteRedirect({
    path: to.path,
    isAuthenticated: auth.isAuthenticated,
    mustChangePassword: auth.mustChangePassword,
    workspaceReady: useAppStore(pinia).workspaceReady,
  })
  return redirect || true
})

app.use(pinia)
```

Modify `frontend/src/App.vue`:

```vue
<script setup>
import { usesMinimalShellRoute } from './lib/routeAccess.js'
import { useAuthStore } from './stores/auth.js'
```

and add:

```javascript
const auth = useAuthStore()
const isMinimalShellRoute = computed(() => usesMinimalShellRoute(route.path))
```

Gate polling and websocket:

```javascript
watch(() => auth.isAuthenticated, (loggedIn) => {
  if (loggedIn) {
    if (!workspaceTimer) {
      workspaceTimer = setInterval(() => {
        void refreshWorkspaceStatus()
      }, 15000)
    }
    connect()
    void refreshWorkspaceStatus()
    return
  }
  clearInterval(workspaceTimer)
  workspaceTimer = null
  disconnect()
  store.resetRuntimeState()
})
```

and replace the unconditional `onMounted()` boot logic with:

```javascript
onMounted(() => {
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
  setupInterceptor((msg, type) => {
    toastRef.value?.show(msg, type)
  })
  if (auth.isAuthenticated) {
    connect()
    void refreshWorkspaceStatus()
    workspaceTimer = setInterval(() => {
      void refreshWorkspaceStatus()
    }, 15000)
  }
  void loadDesktopInfo()
})
```

and in template replace `isImportRoute` with `isMinimalShellRoute`.

- [ ] **Step 4: Run the frontend auth tests**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm test -- src/stores/auth.test.js src/lib/routeAccess.test.js"
timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m unittest tests.test_frontend_ui_structure -v"
```

Expected:

- PASS for auth-store persistence and route redirects
- PASS for router and minimal-shell structure assertions

- [ ] **Step 5: Commit the frontend auth shell**

```bash
git add frontend/src/lib/authSession.js frontend/src/lib/routeAccess.js frontend/src/stores/auth.js frontend/src/views/LoginView.vue frontend/src/views/ChangePasswordView.vue frontend/src/services/api.js frontend/src/composables/useWebSocket.js frontend/src/stores/app.js frontend/src/main.js frontend/src/App.vue frontend/src/stores/auth.test.js frontend/src/lib/routeAccess.test.js tests/test_frontend_ui_structure.py
git commit -m "feat: add frontend login and session shell"
```

---

### Task 7: Define Red Tests For Saved-Host Import UI

**Files:**
- Modify: `tests/test_import_layer_structure.py`
- Create: `frontend/src/lib/importWorkbench.test.js`
- Test: `tests/test_import_layer_structure.py`
- Test: `frontend/src/lib/importWorkbench.test.js`

- [ ] **Step 1: Extend structure tests for the saved-host stage**

Append to `tests/test_import_layer_structure.py`:

```python
    def test_import_workbench_includes_saved_hosts_stage(self):
        text = (ROOT / "frontend/src/lib/importWorkbench.js").read_text(encoding="utf-8")
        self.assertIn("已保存主机", text)

        view_text = (ROOT / "frontend/src/views/ImportWorkspace.vue").read_text(encoding="utf-8")
        self.assertIn("ImportSavedHostsStage", view_text)

    def test_saved_host_stage_component_exists(self):
        target = ROOT / "frontend/src/components/import/ImportSavedHostsStage.vue"
        self.assertTrue(target.exists())
```

Create `frontend/src/lib/importWorkbench.test.js`:

```javascript
import test from 'node:test'
import assert from 'node:assert/strict'
import { IMPORT_STAGE_TABS, resolveSavedHostsScopeLabel } from './importWorkbench.js'

test('import stage tabs expose saved hosts first', () => {
  assert.equal(IMPORT_STAGE_TABS[0].key, 'savedHosts')
  assert.equal(IMPORT_STAGE_TABS[0].label, '已保存主机')
})

test('resolveSavedHostsScopeLabel formats mine and all scopes', () => {
  assert.equal(resolveSavedHostsScopeLabel('mine'), '我的主机')
  assert.equal(resolveSavedHostsScopeLabel('all'), '全部用户主机')
})
```

- [ ] **Step 2: Run the red saved-host UI tests**

Run:

```bash
timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m unittest tests.test_import_layer_structure -v"
cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm test -- src/lib/importWorkbench.test.js"
```

Expected:

- FAIL because the saved-host stage component and helper are not present yet
- FAIL because `IMPORT_STAGE_TABS` still starts with `连接来源`

- [ ] **Step 3: Commit the red UI tests**

```bash
git add tests/test_import_layer_structure.py frontend/src/lib/importWorkbench.test.js
git commit -m "test: define saved host import stage"
```

---

### Task 8: Implement The Saved-Host Stage In The Import Workspace

**Files:**
- Create: `frontend/src/composables/useSavedHosts.js`
- Create: `frontend/src/components/import/ImportSavedHostsStage.vue`
- Modify: `frontend/src/lib/importWorkbench.js`
- Modify: `frontend/src/components/import/ImportPrepTabs.vue`
- Modify: `frontend/src/views/ImportWorkspace.vue`
- Modify: `frontend/src/services/api.js`
- Test: `tests/test_import_layer_structure.py`
- Test: `frontend/src/lib/importWorkbench.test.js`

- [ ] **Step 1: Add saved-host helpers and the saved-host stage component**

Modify `frontend/src/lib/importWorkbench.js`:

```javascript
export const IMPORT_STAGE_TABS = Object.freeze([
  { key: 'savedHosts', label: '已保存主机' },
  { key: 'source', label: '新建连接' },
  { key: 'hardware', label: '硬件概览' },
  { key: 'selection', label: '选卡导入' },
])

export function resolveSavedHostsScopeLabel(scope = 'mine') {
  return scope === 'all' ? '全部用户主机' : '我的主机'
}
```

Create `frontend/src/components/import/ImportSavedHostsStage.vue`:

```vue
<script setup>
const props = defineProps({
  hosts: { type: Array, required: true },
  scope: { type: String, required: true },
  loading: { type: Boolean, required: true },
  scanBusyId: { type: Number, default: 0 },
  deleteBusyId: { type: Number, default: 0 },
  canViewAll: { type: Boolean, required: true },
})

const emit = defineEmits(['update:scope', 'scan', 'delete'])
</script>

<template>
  <section class="import-saved-hosts-stage">
    <header class="import-saved-hosts-stage__toolbar">
      <div class="import-saved-hosts-stage__scope" v-if="props.canViewAll">
        <button type="button" class="btn-tech" :class="{ 'btn-tech--primary': props.scope === 'mine' }" @click="emit('update:scope', 'mine')">我的主机</button>
        <button type="button" class="btn-tech" :class="{ 'btn-tech--primary': props.scope === 'all' }" @click="emit('update:scope', 'all')">全部用户主机</button>
      </div>
    </header>
    <div class="import-saved-hosts-stage__grid">
      <article v-for="host in props.hosts" :key="host.id" class="import-saved-hosts-stage__card tech-card">
        <div class="import-saved-hosts-stage__title">{{ host.label }}</div>
        <div class="import-saved-hosts-stage__meta">{{ host.provider_type }} · {{ host.host || host.agent_url }}</div>
        <div class="import-saved-hosts-stage__meta">用户 {{ host.username || '-' }} · Owner {{ host.owner_username || '-' }}</div>
        <div class="import-saved-hosts-stage__actions">
          <button type="button" class="btn-tech btn-tech--primary" :disabled="props.scanBusyId === host.id" @click="emit('scan', host)">直接扫描</button>
          <button type="button" class="btn-tech" :disabled="props.deleteBusyId === host.id" @click="emit('delete', host)">删除</button>
        </div>
      </article>
    </div>
  </section>
</template>
```

- [ ] **Step 2: Add saved-host state management and wire it into `ImportWorkspace.vue`**

Create `frontend/src/composables/useSavedHosts.js`:

```javascript
import { ref } from 'vue'
import { deleteSavedHost, getSavedHosts, scanImportContext } from '../services/api.js'

export function useSavedHosts() {
  const hosts = ref([])
  const scope = ref('mine')
  const loading = ref(false)
  const scanBusyId = ref(0)
  const deleteBusyId = ref(0)

  async function refresh() {
    loading.value = true
    try {
      const { data } = await getSavedHosts(scope.value)
      hosts.value = data.hosts || []
    } finally {
      loading.value = false
    }
  }

  async function scan(host) {
    scanBusyId.value = host.id
    try {
      return await scanImportContext({ saved_host_id: host.id })
    } finally {
      scanBusyId.value = 0
    }
  }

  async function remove(host) {
    deleteBusyId.value = host.id
    try {
      await deleteSavedHost(host.id)
      await refresh()
    } finally {
      deleteBusyId.value = 0
    }
  }

  return { hosts, scope, loading, scanBusyId, deleteBusyId, refresh, scan, remove }
}
```

Modify `frontend/src/views/ImportWorkspace.vue`:

```vue
<script setup>
import { useAuthStore } from '../stores/auth.js'
import { useSavedHosts } from '../composables/useSavedHosts.js'
import ImportSavedHostsStage from '../components/import/ImportSavedHostsStage.vue'
```

and add state:

```javascript
const auth = useAuthStore()
const savedHosts = useSavedHosts()
const activeStage = ref('savedHosts')
const selectedSavedHostId = ref(0)
```

load hosts on mount:

```javascript
onMounted(() => {
  void Promise.all([
    refreshContext().catch(() => {}),
    savedHosts.refresh().catch(() => {}),
  ])
})
```

add direct scan handler:

```javascript
async function handleSavedHostScan(host) {
  feedback.value = null
  try {
    const { data } = await savedHosts.scan(host)
    selectedSavedHostId.value = host.id
    scanResult.value = data
    selectedGpuIndexes.value = data.success ? data.gpus.map((gpu) => Number(gpu.index)) : []
    feedback.value = { tone: data.success ? 'ok' : 'warning', text: data.message || '扫描完成' }
    if (data.success) {
      activeStage.value = 'hardware'
    }
  } catch (error) {
    feedback.value = {
      tone: 'error',
      text: error?.response?.data?.detail || error?.message || '扫描失败',
    }
  }
}
```

and update `handleScan()` and `handleImport()`:

```javascript
async function handleScan() {
  selectedSavedHostId.value = 0
  scanBusy.value = true
  feedback.value = null
  try {
    const { data } = await scanImportContext(payloadBase())
    scanResult.value = data
    hostFingerprint.value = data?.provider?.host_fingerprint || data?.capabilities?.host_fingerprint || ''
    selectedGpuIndexes.value = data.success ? data.gpus.map((gpu) => Number(gpu.index)) : []
    feedback.value = {
      tone: data.success ? 'ok' : 'warning',
      text: data.message || (data.success ? '扫描完成，已更新候选硬件列表。' : '扫描失败'),
    }
    if (data.success) activeStage.value = 'hardware'
  } catch (error) {
    feedback.value = {
      tone: 'error',
      text: error?.response?.data?.detail || error?.message || '扫描失败',
    }
  } finally {
    scanBusy.value = false
  }
}

async function handleImport() {
  importBusy.value = true
  feedback.value = null
  try {
    const payload = selectedSavedHostId.value
      ? { saved_host_id: selectedSavedHostId.value, gpu_indexes: selectedGpuIndexes.value }
      : { ...payloadBase(), gpu_indexes: selectedGpuIndexes.value }
    const { data } = await commitImportContext(payload)
    store.setImportContext(data.import_context)
    store.setWorkspaceReady(true)
    router.replace('/')
  } catch (error) {
    feedback.value = {
      tone: 'error',
      text: error?.response?.data?.detail || error?.message || '导入失败',
    }
    activeStage.value = 'selection'
  } finally {
    importBusy.value = false
  }
}
```

and add the stage in the template:

```vue
      <ImportSavedHostsStage
        v-if="activeStage === 'savedHosts'"
        :hosts="savedHosts.hosts"
        :scope="savedHosts.scope"
        :loading="savedHosts.loading"
        :scan-busy-id="savedHosts.scanBusyId"
        :delete-busy-id="savedHosts.deleteBusyId"
        :can-view-all="auth.user?.role === 'admin'"
        @update:scope="savedHosts.scope = $event; savedHosts.refresh()"
        @scan="handleSavedHostScan"
        @delete="savedHosts.remove"
      />
```

Modify `frontend/src/components/import/ImportPrepTabs.vue` aria label:

```javascript
const IMPORT_PREP_TAB_ARIA_LABEL = '已保存主机 / 新建连接 / 硬件概览 / 选卡导入'
```

- [ ] **Step 3: Run the import UI tests and frontend build**

Run:

```bash
timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m unittest tests.test_import_layer_structure tests.test_frontend_ui_structure -v"
cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm test -- src/lib/importWorkbench.test.js src/stores/auth.test.js src/lib/routeAccess.test.js src/stores/app.test.js"
cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm run build"
```

Expected:

- PASS for saved-host stage structure and helper tests
- PASS for auth, route-access, and app-store tests
- PASS for Vite production build

- [ ] **Step 4: Commit the saved-host import UI**

```bash
git add frontend/src/composables/useSavedHosts.js frontend/src/components/import/ImportSavedHostsStage.vue frontend/src/lib/importWorkbench.js frontend/src/components/import/ImportPrepTabs.vue frontend/src/views/ImportWorkspace.vue frontend/src/lib/importWorkbench.test.js tests/test_import_layer_structure.py tests/test_frontend_ui_structure.py
git commit -m "feat: add saved host stage to import workspace"
```

---

### Task 9: Run Full Regression Verification

**Files:**
- Verify only: no new source files in this task

- [ ] **Step 1: Run backend regression tests**

Run:

```bash
timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m unittest tests.test_platform_identity_flow tests.test_encrypted_credential_store tests.test_credential_store tests.test_saved_host_service tests.test_ssh_import_flow tests.test_import_layer_structure tests.test_frontend_ui_structure -v"
timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m pytest backend/tests/test_auth.py -v"
```

Expected:

- PASS for all platform identity, encrypted credential, saved-host, import-flow, and structure tests

- [ ] **Step 2: Run frontend regression tests and build**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm test -- src/stores/auth.test.js src/lib/routeAccess.test.js src/lib/importWorkbench.test.js src/stores/app.test.js src/lib/importContext.test.js"
cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm run build"
```

Expected:

- PASS for node-based frontend tests
- PASS for Vite build, with warnings allowed only if they are existing chunk-size warnings

- [ ] **Step 3: Run Python bytecode verification**

Run:

```bash
timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m compileall backend/app"
```

Expected:

- PASS with no syntax errors

- [ ] **Step 4: Inspect git status before final commit**

Run:

```bash
git status --short
```

Expected:

- Only the files listed in this plan are modified for this feature
- No accidental edits in unrelated runtime or generated files

- [ ] **Step 5: Commit the fully verified feature**

```bash
git add backend/requirements.txt backend/app/main.py backend/app/models/schemas.py backend/app/middleware/auth.py backend/app/api/auth_access.py backend/app/api/auth.py backend/app/api/admin_users.py backend/app/api/hosts.py backend/app/api/system.py backend/app/services/password_hasher.py backend/app/services/credential_cipher.py backend/app/services/platform_identity_store.py backend/app/services/platform_auth_service.py backend/app/services/saved_host_service.py backend/app/services/credential_store.py tests/test_platform_identity_flow.py tests/test_saved_host_service.py tests/test_encrypted_credential_store.py tests/test_credential_store.py tests/test_ssh_import_flow.py backend/tests/test_auth.py frontend/src/lib/authSession.js frontend/src/lib/routeAccess.js frontend/src/lib/importWorkbench.js frontend/src/lib/routeAccess.test.js frontend/src/lib/importWorkbench.test.js frontend/src/stores/auth.js frontend/src/stores/auth.test.js frontend/src/stores/app.js frontend/src/views/LoginView.vue frontend/src/views/ChangePasswordView.vue frontend/src/views/ImportWorkspace.vue frontend/src/composables/useSavedHosts.js frontend/src/composables/useWebSocket.js frontend/src/components/import/ImportPrepTabs.vue frontend/src/components/import/ImportSavedHostsStage.vue frontend/src/services/api.js frontend/src/main.js frontend/src/App.vue tests/test_import_layer_structure.py tests/test_frontend_ui_structure.py
git commit -m "feat: add platform login and saved host reuse"
```
