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


def write_csv(path: Path, samples: list[dict]) -> None:
    import csv

    fieldnames = list(samples[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(samples)
