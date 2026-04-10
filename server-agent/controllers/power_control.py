"""GPU功耗控制 - 通过nvidia-smi设置Power Limit"""

import logging
import re
import subprocess

from config import POWER_LIMIT_MIN, POWER_LIMIT_MAX

logger = logging.getLogger(__name__)

_UNSUPPORTED_WRITE_MARKERS = (
    "not supported in current scope",
    "power management limit is not supported",
    "changing power management limit is not supported",
    "not supported for gpu",
)


def _merge_output(result: subprocess.CompletedProcess) -> str:
    parts = []
    if result.stdout:
        parts.append(result.stdout.strip())
    if result.stderr:
        parts.append(result.stderr.strip())
    return "\n".join(part for part in parts if part)


def _run_nvidia_smi(command: list[str], timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout)


def _looks_unsupported(output: str) -> bool:
    lowered = output.lower()
    return any(marker in lowered for marker in _UNSUPPORTED_WRITE_MARKERS)


def _parse_power_limit(output: str) -> float | None:
    value = (output or "").strip()
    if not value:
        return None
    first_line = value.splitlines()[0].strip()
    if not first_line or "n/a" in first_line.lower():
        return None
    match = re.search(r"(-?\d+(?:\.\d+)?)", first_line)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _read_power_limit(gpu_index: int) -> float | None:
    query = [
        "nvidia-smi",
        "-i",
        str(gpu_index),
        "--query-gpu=power.limit",
        "--format=csv,noheader,nounits",
    ]
    result = _run_nvidia_smi(query, timeout=10)
    if result.returncode != 0:
        logger.warning("GPU%s 功耗上限回读失败: %s", gpu_index, _merge_output(result))
        return None
    return _parse_power_limit(result.stdout)


def set_power_limit(gpu_index: int, power_watts: int) -> dict:
    """设置指定GPU的功耗上限"""
    if power_watts < POWER_LIMIT_MIN or power_watts > POWER_LIMIT_MAX:
        return {
            "success": False,
            "error": f"功耗限制必须在 {POWER_LIMIT_MIN}W - {POWER_LIMIT_MAX}W 之间",
        }

    cmd = ["nvidia-smi", "-i", str(gpu_index), "-pl", str(power_watts)]
    try:
        result = _run_nvidia_smi(cmd, timeout=10)
        output = _merge_output(result)
        if result.returncode != 0:
            return {"success": False, "error": output or "设置功耗限制失败"}
        if _looks_unsupported(output):
            return {"success": False, "error": output or "当前环境不支持修改GPU功耗上限"}

        applied_limit = _read_power_limit(gpu_index)
        if applied_limit is None:
            return {"success": False, "error": "功耗限制写入后无法回读当前值，已拒绝判定为成功"}

        if abs(applied_limit - float(power_watts)) > 0.6:
            return {
                "success": False,
                "error": (
                    f"功耗限制写入未生效：目标 {power_watts}W，"
                    f"当前仍为 {applied_limit:.1f}W"
                ),
            }

        logger.info("GPU%s 功耗限制已设置为 %.1fW", gpu_index, applied_limit)
        return {
            "success": True,
            "gpu_index": gpu_index,
            "power_limit": power_watts,
            "applied_power_limit": round(applied_limit, 1),
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "命令超时"}
    except Exception as e:
        return {"success": False, "error": str(e)}
