from __future__ import annotations

from app.services.ssh_linux_parsers import calculate_cpu_percent


def _to_int(value: str, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _to_float(value: str, default: float = 0.0) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def parse_proc_stat_snapshot(raw: str) -> tuple[tuple[int, int], list[tuple[int, int]]]:
    aggregate = None
    per_core = []
    for line in raw.splitlines():
        if not line.startswith("cpu"):
            continue
        parts = line.split()
        values = [_to_int(item) for item in parts[1:]]
        total = sum(values)
        idle = values[3] + (values[4] if len(values) > 4 else 0)
        if parts[0] == "cpu":
            aggregate = (total, idle)
            continue
        if parts[0][3:].isdigit():
            per_core.append((total, idle))
    if aggregate is None:
        raise ValueError("missing cpu aggregate row in /proc/stat output")
    return aggregate, per_core


def calculate_cpu_per_core(
    previous: list[tuple[int, int]],
    current: list[tuple[int, int]],
) -> list[float]:
    return [
        calculate_cpu_percent(prev, curr)
        for prev, curr in zip(previous, current)
    ]


def parse_cpuinfo_physical_count(raw: str, fallback: int) -> int:
    cores = set()
    block = {}
    for line in raw.splitlines() + [""]:
        if ":" not in line:
            if block:
                socket = block.get("physical id", "0")
                core = block.get("core id")
                if core is not None:
                    cores.add((socket, core))
                block = {}
            continue
        key, value = line.split(":", 1)
        block[key.strip()] = value.strip()
    return len(cores) or int(fallback)


def parse_uptime_seconds(raw: str) -> float:
    return _to_float(raw.split()[0] if raw.split() else "0")


def parse_disk_rows(raw: str) -> list[dict]:
    rows = []
    for line in raw.splitlines()[1:]:
        parts = line.split(None, 6)
        if len(parts) != 7:
            continue
        rows.append(
            {
                "device": parts[0],
                "mountpoint": parts[1],
                "fstype": parts[2],
                "total": _to_int(parts[3]),
                "used": _to_int(parts[4]),
                "free": _to_int(parts[5]),
                "percent": _to_float(parts[6].rstrip("%")),
            }
        )
    return rows


def parse_network_counters(raw: str) -> dict:
    totals = {
        "bytes_sent": 0,
        "bytes_recv": 0,
        "packets_sent": 0,
        "packets_recv": 0,
    }
    for line in raw.splitlines():
        if ":" not in line:
            continue
        _, payload = line.split(":", 1)
        fields = payload.split()
        if len(fields) < 10:
            continue
        totals["bytes_recv"] += _to_int(fields[0])
        totals["packets_recv"] += _to_int(fields[1])
        totals["bytes_sent"] += _to_int(fields[8])
        totals["packets_sent"] += _to_int(fields[9])
    return totals
