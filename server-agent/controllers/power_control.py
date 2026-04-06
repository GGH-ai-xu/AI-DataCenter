"""GPU功耗控制 - 通过nvidia-smi设置Power Limit"""

import logging
import subprocess

from config import POWER_LIMIT_MIN, POWER_LIMIT_MAX

logger = logging.getLogger(__name__)


def set_power_limit(gpu_index: int, power_watts: int) -> dict:
    """设置指定GPU的功耗上限"""
    if power_watts < POWER_LIMIT_MIN or power_watts > POWER_LIMIT_MAX:
        return {
            "success": False,
            "error": f"功耗限制必须在 {POWER_LIMIT_MIN}W - {POWER_LIMIT_MAX}W 之间",
        }

    cmd = ["nvidia-smi", "-i", str(gpu_index), "-pl", str(power_watts)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            logger.info(f"GPU{gpu_index} 功耗限制设置为 {power_watts}W")
            return {"success": True, "gpu_index": gpu_index, "power_limit": power_watts}
        else:
            return {"success": False, "error": result.stderr.strip()}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "命令超时"}
    except Exception as e:
        return {"success": False, "error": str(e)}
