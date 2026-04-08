from __future__ import annotations

import re
from collections.abc import Awaitable, Callable

from app.services.ssh_linux_parsers import (
    build_unavailable_gpu_row,
    parse_gpu_list_rows,
    parse_gpu_rows,
)


GPU_LIST_QUERY = "nvidia-smi -L"
UNKNOWN_GPU_NAME = "Unknown GPU"
GPU_PROCESS_FIELDS = "pid,gpu_uuid,used_memory"
GPU_METRIC_FIELDS = (
    "index,uuid,name,pci.bus_id,temperature.gpu,power.draw,power.limit,"
    "utilization.gpu,utilization.memory,memory.used,memory.total,memory.free,"
    "fan.speed,clocks.current.sm,clocks.current.memory"
)
GPU_ERROR_BUS_ID_PATTERN = re.compile(r"GPU(?P<bus_id>(?:[0-9A-Fa-f]{4,8}:)?[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}\.[0-9A-Fa-f])")
GPU_LIST_ERROR_PATTERN = re.compile(
    r"Unable to determine the device handle for gpu\s*"
    r"(?P<bus_id>(?:[0-9A-Fa-f]{4,8}:)?[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}\.[0-9A-Fa-f])"
    r"\s*:\s*(?P<reason>.+)$",
    re.IGNORECASE,
)


def build_gpu_metrics_query(gpu_index: int) -> str:
    return (
        f"nvidia-smi -i {int(gpu_index)} "
        f"--query-gpu={GPU_METRIC_FIELDS} "
        "--format=csv,noheader,nounits"
    )


def build_gpu_process_query(gpu_index: int) -> str:
    return (
        f"nvidia-smi -i {int(gpu_index)} "
        f"--query-compute-apps={GPU_PROCESS_FIELDS} "
        "--format=csv,noheader,nounits"
    )


def command_error_message(result, command: str) -> str:
    stderr = result.stderr.strip()
    if stderr:
        return stderr
    stdout = result.stdout.strip()
    if stdout:
        return f"{stdout} (command: {command})"
    return f"command failed: {command}"


def build_gpu_collection_error(failures: list[dict]) -> str:
    details = "；".join(
        f"GPU {item['index']}({item['name']}): {item['error']}"
        for item in failures
    )
    return f"未发现可用 GPU：{details}" if details else "未发现可用 GPU"


def _identity_with_bus_id(identity: dict, error: str) -> dict:
    if identity.get("pci_bus_id"):
        return dict(identity)
    match = GPU_ERROR_BUS_ID_PATTERN.search(error)
    if not match:
        return dict(identity)
    next_identity = dict(identity)
    next_identity["pci_bus_id"] = match.group("bus_id")
    return next_identity


def _gpu_list_output(result) -> str:
    parts = [str(result.stdout or "").strip(), str(result.stderr or "").strip()]
    return "\n".join(part for part in parts if part)


def _inventory_missing_indexes(identities: list[dict], missing_count: int) -> list[int]:
    seen = sorted(
        int(identity["index"])
        for identity in identities
        if int(identity.get("index", -1)) >= 0
    )
    if not seen:
        return list(range(missing_count))
    max_seen = seen[-1]
    seen_set = set(seen)
    missing = [index for index in range(max_seen + 1) if index not in seen_set]
    next_index = max_seen + 1
    while len(missing) < missing_count:
        missing.append(next_index)
        next_index += 1
    return missing[:missing_count]


def parse_gpu_inventory(result, timestamp: float) -> tuple[list[dict], list[dict], list[dict]]:
    raw_output = _gpu_list_output(result)
    identities = parse_gpu_list_rows(raw_output)
    matches = [
        GPU_LIST_ERROR_PATTERN.search(line.strip())
        for line in raw_output.splitlines()
        if line.strip()
    ]
    failures = [match for match in matches if match]
    missing_indexes = _inventory_missing_indexes(identities, len(failures))
    unavailable_rows = []
    failure_details = []
    for offset, match in enumerate(failures):
        index = missing_indexes[offset] if offset < len(missing_indexes) else -1
        error = match.group(0).strip()
        identity = {
            "index": index,
            "name": UNKNOWN_GPU_NAME,
            "uuid": "",
            "pci_bus_id": match.group("bus_id"),
        }
        unavailable_rows.append(build_unavailable_gpu_row(identity, error, timestamp))
        failure_details.append({"index": index, "name": UNKNOWN_GPU_NAME, "error": error})
    return identities, unavailable_rows, failure_details


def _sort_gpu_rows(rows: list[dict]) -> list[dict]:
    return sorted(
        rows,
        key=lambda row: (
            int(row.get("index", -1) < 0),
            int(row.get("index", -1)),
        ),
    )


def _log_failed_commands(log_failed_command, failed_commands: list[tuple[object, str]]) -> None:
    for result, command in failed_commands:
        log_failed_command(result, command)


async def collect_gpu_process_output(
    run_command: Callable[[str], Awaitable],
    log_failed_command: Callable[[object, str], None],
    identities: list[dict],
) -> str:
    outputs = []
    success_count = 0
    failed_commands = []
    for identity in identities:
        command = build_gpu_process_query(identity["index"])
        result = await run_command(command)
        if result.code == 0:
            success_count += 1
            stdout = result.stdout.strip()
            if stdout:
                outputs.append(stdout)
            continue
        failed_commands.append((result, command))
    if success_count > 0:
        return "\n".join(outputs)
    if failed_commands:
        _log_failed_commands(log_failed_command, failed_commands)
        first_result, first_command = failed_commands[0]
        raise RuntimeError(command_error_message(first_result, first_command))
    return ""


async def collect_gpu_rows(
    run_command: Callable[[str], Awaitable],
    log_failed_command: Callable[[object, str], None],
    timestamp: float,
) -> list[dict]:
    inventory_result = await run_command(GPU_LIST_QUERY)
    identities, rows, failures = parse_gpu_inventory(inventory_result, timestamp)
    failed_commands = []
    if inventory_result.code != 0:
        if not identities and not failures:
            log_failed_command(inventory_result, GPU_LIST_QUERY)
            raise RuntimeError(command_error_message(inventory_result, GPU_LIST_QUERY))
        failed_commands.append((inventory_result, GPU_LIST_QUERY))
    for identity in identities:
        command = build_gpu_metrics_query(identity["index"])
        result = await run_command(command)
        if result.code == 0:
            rows.extend(parse_gpu_rows(result.stdout, timestamp))
            continue
        failed_commands.append((result, command))
        error = command_error_message(result, command)
        rows.append(
            build_unavailable_gpu_row(
                _identity_with_bus_id(identity, error),
                error,
                timestamp,
            )
        )
        failures.append(
            {
                "index": identity["index"],
                "name": identity["name"],
                "error": error,
            }
        )
    if any(row.get("available", True) for row in rows):
        return _sort_gpu_rows(rows)
    _log_failed_commands(log_failed_command, failed_commands)
    raise RuntimeError(build_gpu_collection_error(failures))
