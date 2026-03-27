"""Windows 后端入口 - 为打包版准备运行时目录与静态资源路径"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn


APP_SLUG = "GPU-Governance-Workbench"


def install_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def runtime_root() -> Path:
    configured = os.getenv("GPU_GOV_HOME", "").strip()
    if configured:
        root = Path(configured)
    else:
        base = Path(os.environ.get("LOCALAPPDATA", install_root() / "runtime"))
        root = base / APP_SLUG
        os.environ["GPU_GOV_HOME"] = str(root)
    return root


def configure_environment():
    root = install_root()
    runtime = runtime_root()
    data_dir = runtime / "data"
    runtime_dir = runtime / "runtime"
    data_dir.mkdir(parents=True, exist_ok=True)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    frontend_dist = root / "frontend" / "dist"
    if not frontend_dist.exists():
        frontend_dist = root / "_internal" / "frontend" / "dist"
    os.environ.setdefault("DB_PATH", str(data_dir / "history.db"))
    os.environ.setdefault("CONNECTION_CONFIG_PATH", str(runtime_dir / "connection.json"))
    os.environ.setdefault("FRONTEND_DIST_DIR", str(frontend_dist))
    os.environ.setdefault("HOST", "127.0.0.1")
    os.environ.setdefault("PORT", "8000")

    if not getattr(sys, "frozen", False):
        sys.path.insert(0, str(root / "backend"))


def main():
    configure_environment()
    from app.main import app

    uvicorn.run(
        app,
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":
    main()
