from __future__ import annotations


MEBIBYTE = 1024 * 1024
UNKNOWN_USER = "unknown"
DEFAULT_PRIORITY = "normal"
GOVERNABLE_REASON = "可作为治理任务处理"


def _normalize_metric(value: str | None) -> str:
    raw = str(value or "").strip().strip("[]")
    if raw.lower() in {"", "n/a", "not supported"}:
        return "0"
    return raw


def _to_int(value: str | None, default: int = 0) -> int:
    try:
        return int(float(_normalize_metric(value)))
    except (TypeError, ValueError):
        return default


def _to_float(value: str | None, default: float = 0.0) -> float:
    try:
        return float(_normalize_metric(value))
    except (TypeError, ValueError):
        return default


def _split_csv_row(line: str) -> list[str]:
    return [part.strip() for part in line.split(",")]


def parse_gpu_rows(raw: str, timestamp: float) -> list[dict]:
    rows = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = _split_csv_row(line)
        (
            index,
            uuid,
            name,
            temperature,
            power_usage,
            power_limit,
            gpu_utilization,
            memory_utilization,
            memory_used,
            memory_total,
            memory_free,
            fan_speed,
            clock_sm,
            clock_mem,
        ) = parts
        rows.append(
            {
                "index": _to_int(index),
                "uuid": uuid,
                "name": name,
                "temperature": _to_int(temperature),
                "power_usage": _to_float(power_usage),
                "power_limit": _to_float(power_limit),
                "gpu_utilization": _to_int(gpu_utilization),
                "memory_utilization": _to_int(memory_utilization),
                "memory_used": _to_int(memory_used),
                "memory_total": _to_int(memory_total),
                "memory_free": _to_int(memory_free),
                "fan_speed": _to_int(fan_speed),
                "clock_sm": _to_int(clock_sm),
                "clock_mem": _to_int(clock_mem),
                "timestamp": timestamp,
            }
        )
    return rows


def parse_gpu_uuid_map(raw: str) -> dict[str, int]:
    mapping = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = _split_csv_row(line)
        if len(parts) < 2:
            continue
        mapping[parts[1]] = _to_int(parts[0], -1)
    return {
        uuid: index
        for uuid, index in mapping.items()
        if uuid and index >= 0
    }


def parse_compute_process_rows(
    raw: str,
    gpu_index_by_uuid: dict[str, int],
) -> list[dict]:
    processes = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = _split_csv_row(line)
        if len(parts) < 3:
            continue
        pid = _to_int(parts[0], -1)
        gpu_uuid = parts[1]
        gpu_index = gpu_index_by_uuid.get(gpu_uuid, -1)
        if pid <= 0 or gpu_index < 0:
            continue
        processes.append(
            {
                "pid": pid,
                "gpu_uuid": gpu_uuid,
                "gpu_index": gpu_index,
                "gpu_memory_used": _to_int(parts[2]) * MEBIBYTE,
            }
        )
    return processes


def parse_ps_rows(raw: str, timestamp: float) -> dict[int, dict]:
    rows = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.strip().split(None, 5)
        if len(parts) < 5:
            continue
        pid = _to_int(parts[0], -1)
        if pid <= 0:
            continue
        user = parts[1] if len(parts) > 1 else UNKNOWN_USER
        name = parts[2] if len(parts) > 2 else ""
        elapsed = _to_float(parts[3]) if len(parts) > 3 else 0.0
        cpu_percent = _to_float(parts[4]) if len(parts) > 4 else 0.0
        command = parts[5] if len(parts) > 5 else name
        rows[pid] = {
            "username": user or UNKNOWN_USER,
            "name": name,
            "command": command,
            "cpu_percent": cpu_percent,
            "create_time": max(0.0, float(timestamp) - elapsed),
        }
    return rows


def parse_proc_stat(raw: str) -> tuple[int, int]:
    for line in raw.splitlines():
        if not line.startswith("cpu "):
            continue
        parts = line.split()
        values = [_to_int(item) for item in parts[1:]]
        total = sum(values)
        idle = values[3] + (values[4] if len(values) > 4 else 0)
        return total, idle
    raise ValueError("missing cpu aggregate row in /proc/stat output")


def calculate_cpu_percent(
    previous: tuple[int, int],
    current: tuple[int, int],
) -> float:
    total_delta = current[0] - previous[0]
    idle_delta = current[1] - previous[1]
    if total_delta <= 0:
        return 0.0
    busy_ratio = (total_delta - idle_delta) / total_delta
    return round(max(0.0, busy_ratio * 100.0), 1)


def parse_meminfo(raw: str) -> dict[str, int]:
    values = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, remainder = line.split(":", 1)
        number = remainder.strip().split()[0] if remainder.strip() else "0"
        values[key.strip()] = _to_int(number) * 1024
    return values


def parse_load_average(raw: str) -> list[float]:
    fields = raw.strip().split()
    return [_to_float(value) for value in fields[:3]]


def build_system_info(
    cpu_count: int,
    cpu_percent: float,
    meminfo: dict[str, int],
    load_average: list[float],
    timestamp: float,
) -> dict:
    memory_total = meminfo.get("MemTotal", 0)
    available = meminfo.get("MemAvailable")
    free = meminfo.get("MemFree", 0)
    memory_used = memory_total - (available if available is not None else free)
    memory_percent = round(memory_used / memory_total * 100.0, 1) if memory_total else 0.0
    return {
        "cpu_percent": cpu_percent,
        "cpu_count": int(cpu_count),
        "memory_total": memory_total,
        "memory_used": max(0, memory_used),
        "memory_percent": memory_percent,
        "load_avg": load_average,
        "timestamp": float(timestamp),
    }


def merge_process_rows(
    compute_rows: list[dict],
    ps_rows: dict[int, dict],
) -> list[dict]:
    merged = []
    for row in compute_rows:
        pid = row["pid"]
        details = ps_rows.get(pid, {})
        merged.append(
            {
                **row,
                "name": details.get("name", ""),
                "username": details.get("username", UNKNOWN_USER),
                "command": details.get("command", ""),
                "cpu_percent": details.get("cpu_percent", 0.0),
                "create_time": details.get("create_time", 0.0),
                "priority": DEFAULT_PRIORITY,
                "manageable": True,
                "process_category": "governable",
                "manageable_reason_code": "governable_task",
                "manageable_summary": "可治理任务",
                "manageable_reason": GOVERNABLE_REASON,
                "is_background_process": False,
            }
        )
    return merged
