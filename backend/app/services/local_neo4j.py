"""本地 Neo4j 启动与重连辅助。"""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
from pathlib import Path
from urllib.parse import urlparse


LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


class LocalNeo4jService:
    def __init__(self, repo_root: str | None = None):
        self.repo_root = Path(repo_root or Path(__file__).resolve().parents[3])
        self.start_script = self.repo_root / "scripts" / "start-local-neo4j.ps1"

    @staticmethod
    def _parse_uri(uri: str) -> tuple[str, int]:
        parsed = urlparse((uri or "").strip())
        host = (parsed.hostname or "").strip().lower()
        port = parsed.port or 7687
        return host, port

    @staticmethod
    def _is_port_open(host: str, port: int) -> bool:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            return False

    def capability(self, uri: str) -> dict:
        if os.name != "nt":
            return {
                "local_start_available": False,
                "local_start_message": "当前系统不是 Windows，无法自动启动本地 Neo4j。",
            }

        if not self.start_script.is_file():
            return {
                "local_start_available": False,
                "local_start_message": "缺少本地 Neo4j 启动脚本，无法执行一键拉起。",
            }

        host, port = self._parse_uri(uri)
        if host not in LOCAL_HOSTS:
            return {
                "local_start_available": False,
                "local_start_message": "当前 Neo4j 不是本机实例，无法自动启动远程图库。",
            }

        return {
            "local_start_available": True,
            "local_start_message": f"可尝试一键启动或重连本地 Neo4j（{host}:{port}）。",
        }

    async def ensure_running(self, uri: str, timeout_seconds: int = 45) -> dict:
        capability = self.capability(uri)
        if not capability["local_start_available"]:
            return {
                "ok": False,
                "started": False,
                "message": capability["local_start_message"],
            }

        host, port = self._parse_uri(uri)
        if self._is_port_open(host, port):
            return {
                "ok": True,
                "started": False,
                "message": f"本地 Neo4j 已在运行（{host}:{port}），准备重连。",
            }

        command = [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(self.start_script),
        ]

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                command,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "started": False,
                "message": "本地 Neo4j 启动超时，请检查 Neo4j 与 JDK 路径配置。",
            }
        except OSError as exc:
            return {
                "ok": False,
                "started": False,
                "message": f"执行本地 Neo4j 启动脚本失败：{exc}",
            }

        output = (result.stdout or "").strip()
        error = (result.stderr or "").strip()
        message = output or error or "本地 Neo4j 启动完成。"
        return {
            "ok": result.returncode == 0,
            "started": result.returncode == 0,
            "message": message,
        }
