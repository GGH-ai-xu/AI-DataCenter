"""Windows 桌面启动器 - 启动后台服务并打开智算中心优化代码生成系统"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


APP_SLUG = "GPU-Governance-Workbench"
LAUNCH_URL = "http://127.0.0.1:8000/"
HEALTH_URL = "http://127.0.0.1:8000/api/health"
LOCAL_AGENT_HEALTH_URL = "http://127.0.0.1:8001/api/health"


def install_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent.parent
    return Path(__file__).resolve().parents[1]


def runtime_root() -> Path:
    configured = os.getenv("GPU_GOV_HOME", "").strip()
    if configured:
        root = Path(configured)
    else:
        base = Path(os.environ.get("LOCALAPPDATA", install_root() / "runtime"))
        root = base / APP_SLUG
        os.environ["GPU_GOV_HOME"] = str(root)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "runtime").mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(parents=True, exist_ok=True)
    return root


def connection_mode(runtime: Path) -> str:
    config_path = runtime / "runtime" / "connection.json"
    if not config_path.exists():
        return "local"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload.get("mode", "local")
    except Exception:
        return "local"


def http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2.5) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def wait_http(url: str, seconds: float) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if http_ok(url):
            return True
        time.sleep(0.8)
    return False


def show_message(text: str, title: str = "智算中心优化代码生成系统"):
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, text, title, 0x40)
            return
        except Exception:
            pass
    print(text)


def start_hidden_process(executable: Path, log_path: Path, env: dict[str, str]):
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    log_file = open(log_path, "a", encoding="utf-8")
    return subprocess.Popen(
        [str(executable)],
        cwd=str(executable.parent),
        stdout=log_file,
        stderr=log_file,
        env=env,
        creationflags=creationflags,
    )


def main():
    root = install_root()
    runtime = runtime_root()
    env = os.environ.copy()
    env["GPU_GOV_HOME"] = str(runtime)

    if http_ok(HEALTH_URL):
        webbrowser.open(LAUNCH_URL)
        return

    mode = connection_mode(runtime)
    backend_exe = root / "backend" / "GPUGovernanceBackend.exe"
    agent_exe = root / "agent" / "GPUServerAgent.exe"

    if not backend_exe.exists():
        show_message(f"未找到后端程序：{backend_exe}")
        return

    if mode == "local" and agent_exe.exists() and not http_ok(LOCAL_AGENT_HEALTH_URL):
        start_hidden_process(agent_exe, runtime / "logs" / "agent.log", env)
        wait_http(LOCAL_AGENT_HEALTH_URL, 12)

    start_hidden_process(backend_exe, runtime / "logs" / "backend.log", env)
    if not wait_http(HEALTH_URL, 18):
        show_message(
            "平台启动超时，请查看日志：\n"
            f"{runtime / 'logs' / 'backend.log'}"
        )
        return

    webbrowser.open(LAUNCH_URL)


if __name__ == "__main__":
    main()
