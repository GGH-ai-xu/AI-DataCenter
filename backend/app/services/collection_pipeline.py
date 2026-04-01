import asyncio
from typing import Any


async def collect_agent_snapshot(agent) -> dict[str, Any]:
    gpus, system, processes = await asyncio.gather(
        agent.get_all_gpus(),
        agent.get_system_info(),
        agent.get_processes(),
    )
    return {
        "gpus": gpus,
        "system": system,
        "processes": processes,
    }


def apply_task_priorities(
    processes: list[dict],
    priorities: dict[int, str],
) -> list[dict]:
    enriched_processes = []
    for proc in processes:
        cloned = dict(proc)
        pid = cloned.get("pid")
        cloned["priority"] = priorities.get(
            pid,
            cloned.get("priority", "normal"),
        )
        enriched_processes.append(cloned)
    return enriched_processes
