from __future__ import annotations

import copy
import time
from typing import Any

from app.services.collection_pipeline import apply_task_priorities
from app.services.runtime_scope import build_realtime_scope


def empty_runtime_snapshot() -> dict[str, Any]:
    return {
        "collected_at": 0.0,
        "agent_health": None,
        "runtime": {},
        "import_context": {},
        "raw": {"system": None, "gpus": [], "processes": []},
        "scoped": {"system": None, "gpus": [], "processes": [], "public_processes": []},
    }


def has_runtime_snapshot(snapshot: dict | None) -> bool:
    return bool((snapshot or {}).get("collected_at"))


def snapshot_collected_at(snapshot: dict | None) -> float:
    return float((snapshot or {}).get("collected_at") or 0.0)


def snapshot_agent_health(snapshot: dict | None) -> dict | None:
    return copy.deepcopy((snapshot or {}).get("agent_health"))


def snapshot_import_context(snapshot: dict | None) -> dict:
    return copy.deepcopy((snapshot or {}).get("import_context") or {})


def snapshot_scoped_system(snapshot: dict | None) -> dict | None:
    return copy.deepcopy(((snapshot or {}).get("scoped") or {}).get("system"))


def snapshot_scoped_gpus(snapshot: dict | None) -> list[dict]:
    return copy.deepcopy((((snapshot or {}).get("scoped") or {}).get("gpus") or []))


def snapshot_scoped_processes(snapshot: dict | None) -> list[dict]:
    return copy.deepcopy((((snapshot or {}).get("scoped") or {}).get("processes") or []))


def build_runtime_snapshot(
    *,
    import_context,
    privacy,
    system: dict | None,
    gpus: list[dict],
    processes: list[dict],
    priorities: dict[int, str],
    agent_health: dict | None,
    runtime_status: dict,
    import_context_state: dict,
) -> dict[str, Any]:
    enriched_processes = apply_task_priorities(processes, priorities)
    scoped = build_realtime_scope(
        import_context=import_context,
        privacy=privacy,
        system=system,
        gpus=gpus,
        processes=enriched_processes,
    )
    return {
        "collected_at": time.time(),
        "agent_health": copy.deepcopy(agent_health),
        "runtime": copy.deepcopy(runtime_status),
        "import_context": copy.deepcopy(import_context_state),
        "raw": copy.deepcopy({"system": system, "gpus": gpus, "processes": enriched_processes}),
        "scoped": copy.deepcopy(scoped),
    }


def build_runtime_failure_snapshot(
    *,
    runtime_status: dict,
    import_context_state: dict,
) -> dict[str, Any]:
    snapshot = empty_runtime_snapshot()
    snapshot["collected_at"] = time.time()
    snapshot["runtime"] = copy.deepcopy(runtime_status)
    snapshot["import_context"] = copy.deepcopy(import_context_state)
    return snapshot
