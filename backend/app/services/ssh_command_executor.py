from __future__ import annotations

from dataclasses import dataclass

import asyncssh

SSH_AUTH_DENIED_MARKER = "permission denied for user"
SSH_TIMEOUT_MARKERS = ("timed out", "winerror 121")
SSH_REFUSED_MARKERS = ("connection refused", "winerror 10061")
SSH_UNREACHABLE_MARKERS = ("no route to host", "network is unreachable")


@dataclass(frozen=True)
class CommandResult:
    code: int
    stdout: str
    stderr: str


class SshCommandExecutor:
    def __init__(self, target, secret: dict | None = None):
        self.target = target
        self.secret = dict(secret or {})
        self._connection = None
        self.server_fingerprint = None

    def _private_keys(self):
        private_key = self.secret.get("private_key")
        if not private_key:
            return None
        passphrase = self.secret.get("private_key_passphrase") or None
        return [asyncssh.import_private_key(private_key, passphrase)]

    def _sudo_input(self, use_sudo: bool) -> str | None:
        if not use_sudo:
            return None
        password = self.secret.get("sudo_password") or ""
        return f"{password}\n"

    def _format_connect_error(self, exc: Exception) -> str:
        raw = str(exc).strip() or exc.__class__.__name__
        lowered = raw.lower()
        host = self.target.host or "unknown-host"
        port = self.target.port or 22
        username = self.target.username or "unknown-user"

        if SSH_AUTH_DENIED_MARKER in lowered:
            return (
                f"SSH 认证失败：目标主机拒绝用户 {username} 登录，"
                "请检查用户名、密码或私钥。"
            )
        if any(marker in lowered for marker in SSH_TIMEOUT_MARKERS):
            return f"SSH 连接超时：无法连接到 {host}:{port}。"
        if any(marker in lowered for marker in SSH_REFUSED_MARKERS):
            return f"SSH 连接被拒绝：{host}:{port} 未接受连接。"
        if any(marker in lowered for marker in SSH_UNREACHABLE_MARKERS):
            return f"SSH 目标不可达：无法到达 {host}:{port}。"
        return f"SSH 连接失败：{raw}"

    async def connect(self) -> None:
        if self._connection is not None:
            return
        client_keys = self._private_keys()
        try:
            self._connection = await asyncssh.connect(
                self.target.host,
                port=self.target.port or 22,
                username=self.target.username,
                known_hosts=None,
                password=self.secret.get("password") or None,
                client_keys=client_keys,
            )
        except Exception as exc:
            raise RuntimeError(self._format_connect_error(exc)) from exc
        actual = self._connection.get_server_host_key().get_fingerprint()
        self.server_fingerprint = actual
        expected = self.target.host_fingerprint
        if expected and actual != expected:
            close = getattr(self._connection, "close", None)
            if callable(close):
                result = close()
                if result is not None:
                    maybe_await = getattr(result, "__await__", None)
                    if callable(maybe_await):
                        await result
            self._connection = None
            self.server_fingerprint = None
            raise ValueError(f"host fingerprint mismatch: {actual}")

    async def close(self) -> None:
        if self._connection is None:
            return
        self._connection.close()
        maybe_wait = getattr(self._connection, "wait_closed", None)
        if callable(maybe_wait):
            await maybe_wait()
        self._connection = None
        self.server_fingerprint = None

    async def run(self, command: str, use_sudo: bool = False, timeout: float = 10.0) -> CommandResult:
        if self._connection is None:
            raise RuntimeError("SSH connection is not established")
        wrapped = f"sudo -S -p '' {command}" if use_sudo else command
        result = await self._connection.run(
            wrapped,
            input=self._sudo_input(use_sudo),
            check=False,
            timeout=timeout,
        )
        return CommandResult(
            code=int(result.exit_status),
            stdout=str(result.stdout or ""),
            stderr=str(result.stderr or ""),
        )
