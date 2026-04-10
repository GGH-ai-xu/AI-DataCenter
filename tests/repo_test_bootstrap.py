from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
VENV_DIR = ROOT / ".venv"


def _prepend_sys_path(path: Path) -> None:
    resolved = str(path.resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)


def _candidate_site_packages() -> list[Path]:
    candidates = [VENV_DIR / "Lib" / "site-packages"]
    lib_dir = VENV_DIR / "lib"
    if lib_dir.exists():
        candidates.extend(path / "site-packages" for path in lib_dir.glob("python*"))
    return candidates


def _ensure_importable(module_name: str) -> bool:
    if importlib.util.find_spec(module_name) is not None:
        return True

    for site_packages in _candidate_site_packages():
        if not site_packages.exists():
            continue
        _prepend_sys_path(site_packages)
        importlib.invalidate_caches()
        if importlib.util.find_spec(module_name) is not None:
            return True

    return False


def prepare_backend_test_env(*required_modules: str) -> list[str]:
    _prepend_sys_path(BACKEND_DIR)
    missing = []
    for module_name in required_modules:
        if not _ensure_importable(module_name):
            missing.append(module_name)
    return missing
