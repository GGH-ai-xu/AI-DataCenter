def normalize_processes(processes: list[dict]) -> list[dict]:
    normalized: dict[int, dict] = {}
    for proc in processes:
        pid = int(proc.get("pid") or 0)
        if pid <= 0:
            continue
        normalized[pid] = {
            "pid": pid,
            "gpu_index": int(proc.get("gpu_index", -1)),
            "username": str(proc.get("username") or "unknown"),
            "command": str(proc.get("command") or ""),
            "gpu_memory_used": int(proc.get("gpu_memory_used") or 0),
        }
    return list(normalized.values())


def build_process_batches(
    processes: list[dict],
    active_rows: dict[int, int],
    timestamp: float,
) -> tuple[list[tuple], list[tuple], list[int]]:
    updates = []
    inserts = []
    current_pids = set()

    for proc in processes:
        pid = proc["pid"]
        current_pids.add(pid)
        row_id = active_rows.get(pid)
        payload = (
            timestamp,
            proc["gpu_index"],
            proc["username"],
            proc["command"],
            proc["gpu_memory_used"],
        )
        if row_id is not None:
            updates.append((*payload, row_id))
            continue
        inserts.append(
            (
                pid,
                proc["gpu_index"],
                proc["username"],
                proc["command"],
                proc["gpu_memory_used"],
                timestamp,
                timestamp,
            )
        )

    stale_ids = [
        row_id
        for pid, row_id in active_rows.items()
        if pid not in current_pids
    ]
    return updates, inserts, stale_ids
