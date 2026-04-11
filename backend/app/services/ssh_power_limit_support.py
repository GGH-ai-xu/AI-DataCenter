from __future__ import annotations

import re

from app.services.ssh_linux_gpu_collection import command_error_message


POWER_LIMIT_READBACK_TOLERANCE_WATTS = 0.6
POWER_LIMIT_UNSUPPORTED_MARKERS = (
    "not supported in current scope",
    "power management limit is not supported",
    "changing power management limit is not supported",
    "not supported for gpu",
)


def build_power_limit_query(gpu_index: int) -> str:
    return (
        f"nvidia-smi -i {int(gpu_index)} "
        "--query-gpu=power.limit "
        "--format=csv,noheader,nounits"
    )


def _combined_output(result) -> str:
    parts = [str(result.stdout or "").strip(), str(result.stderr or "").strip()]
    return "\n".join(part for part in parts if part)


def _parse_power_limit(output: str) -> float | None:
    raw = str(output or "").strip()
    if not raw:
        return None
    first_line = raw.splitlines()[0].strip()
    if not first_line or "n/a" in first_line.lower():
        return None
    match = re.search(r"(-?\d+(?:\.\d+)?)", first_line)
    if not match:
        return None
    return float(match.group(1))


def validate_power_limit_write(result, command: str) -> str:
    output = _combined_output(result)
    if int(result.code) != 0:
        return command_error_message(result, command)
    lowered = output.lower()
    if any(marker in lowered for marker in POWER_LIMIT_UNSUPPORTED_MARKERS):
        return output or "当前环境不支持修改 GPU 功耗上限"
    return ""


def validate_power_limit_readback(
    result,
    command: str,
    target_watts: int,
) -> tuple[float | None, str]:
    if int(result.code) != 0:
        error = command_error_message(result, command)
        return None, f"功耗限制写入后回读失败：{error}"
    applied_limit = _parse_power_limit(result.stdout)
    if applied_limit is None:
        return None, "功耗限制写入后无法回读当前值，已拒绝判定为成功"
    if abs(applied_limit - float(target_watts)) > POWER_LIMIT_READBACK_TOLERANCE_WATTS:
        return (
            applied_limit,
            f"功耗限制写入未生效：目标 {target_watts}W，当前仍为 {applied_limit:.1f}W",
        )
    return applied_limit, ""
