from __future__ import annotations

import shlex
import time
from pathlib import Path

POWER_ALERT_THRESHOLD = 320
SAFE_IDLE_POWER_WATTS = 60.0
LOAD_WAIT_TIMEOUT_SECONDS = 80
POST_ACTION_SAMPLES = 18
SAMPLE_INTERVAL_SECONDS = 2.0

REMOTE_SCRIPT = """import time
import torch

torch.backends.cuda.matmul.allow_tf32 = True
torch.set_float32_matmul_precision('high')
device = torch.device('cuda')
size = 24576
dtype = torch.float16
a = torch.randn((size, size), device=device, dtype=dtype)
b = torch.randn((size, size), device=device, dtype=dtype)
out = torch.empty((size, size), device=device, dtype=dtype)
deadline = time.time() + 180
count = 0
while time.time() < deadline:
    torch.matmul(a, b, out=out)
    torch.cuda.synchronize()
    count += 1
    if count % 2 == 0:
        print(f"{time.time():.3f},{count}", flush=True)
"""


def build_remote_paths(gpu_index: int) -> tuple[str, str]:
    stamp = int(time.time())
    base = f"/tmp/aidc_budget_gpu{gpu_index}_{stamp}"
    return f"{base}.py", f"{base}.log"


def shell_wrap(command: str) -> str:
    return f"bash -lc {shlex.quote(command)}"


def summarize_window(samples: list[dict]) -> dict:
    values = [sample["power_usage"] for sample in samples]
    temps = [sample["temperature"] for sample in samples]
    return {
        "sample_count": len(samples),
        "avg_power": round(sum(values) / len(values), 2),
        "peak_power": round(max(values), 2),
        "avg_temperature": round(sum(temps) / len(temps), 2),
        "above_alert_samples": sum(1 for sample in samples if sample["above_power_alert"]),
    }


def compute_budget_limit(peak_sample: dict) -> int:
    excess = max(50, min(80, int(round(peak_sample["power_usage"] * 0.18))))
    return max(400, int(round(peak_sample["total_power"] - excess)))


def ensure_safe_gpu(gpus: list[dict], gpu_index: int) -> dict:
    target = next((gpu for gpu in gpus if int(gpu.get("index", -1)) == gpu_index), None)
    if target is None:
        raise RuntimeError(f"GPU {gpu_index} 不存在")
    if float(target.get("power_usage", 0) or 0) > SAFE_IDLE_POWER_WATTS:
        raise RuntimeError(
            f"GPU {gpu_index} 当前功耗 {target.get('power_usage')}W，超过安全空闲阈值 {SAFE_IDLE_POWER_WATTS}W"
        )
    if int(target.get("gpu_utilization", 0) or 0) > 10:
        raise RuntimeError(f"GPU {gpu_index} 当前利用率非空闲：{target.get('gpu_utilization')}%")
    return target


def find_idle_gpu_candidates(gpus: list[dict], minimum_count: int = 2) -> list[dict]:
    candidates = [
        gpu
        for gpu in gpus
        if float(gpu.get("power_usage", 0) or 0) <= SAFE_IDLE_POWER_WATTS
        and int(gpu.get("gpu_utilization", 0) or 0) <= 10
    ]
    return sorted(candidates, key=lambda item: int(item.get("index", -1)))[:minimum_count]


def choose_governance_pair(gpus: list[dict]) -> tuple[dict, dict]:
    candidates = find_idle_gpu_candidates(gpus, minimum_count=2)
    if len(candidates) < 2:
        raise RuntimeError("空闲 GPU 少于 2 张，无法执行双 GPU 实验")
    return candidates[0], candidates[1]


def summarize_role_window(samples: list[dict], role: str, phase: str) -> dict:
    role_samples = [
        item
        for item in samples
        if str(item.get("gpu_role") or "") == role
        and str(item.get("phase") or "") == phase
    ]
    if not role_samples:
        raise RuntimeError(f"未找到 role={role}, phase={phase} 的样本")
    return summarize_window(role_samples)


def compute_transition_latency(samples: list[dict], role: str, threshold: float) -> dict:
    role_samples = [
        item
        for item in samples
        if str(item.get("gpu_role") or "") == role
    ]
    first_alert = next(
        (item for item in role_samples if bool(item.get("above_power_alert", False))),
        None,
    )
    first_action = next(
        (item for item in role_samples if str(item.get("phase") or "") == "post_action"),
        None,
    )
    first_safe = next(
        (
            item
            for item in role_samples
            if str(item.get("phase") or "") == "post_action"
            and float(item.get("power_usage", 0) or 0) < threshold
        ),
        None,
    )
    return {
        "first_alert_elapsed_s": first_alert["elapsed_s"] if first_alert else None,
        "action_elapsed_s": first_action["elapsed_s"] if first_action else None,
        "first_safe_elapsed_s": first_safe["elapsed_s"] if first_safe else None,
        "recovery_latency_s": (
            round(first_safe["elapsed_s"] - first_action["elapsed_s"], 2)
            if first_safe and first_action
            else None
        ),
    }


def write_csv(path: Path, samples: list[dict]) -> None:
    import csv

    fieldnames = list(samples[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(samples)
