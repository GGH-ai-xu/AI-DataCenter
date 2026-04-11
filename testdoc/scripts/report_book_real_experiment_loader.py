from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "testdoc" / "data"
REAL_JSON_PATH = DATA_DIR / "real_remote_budget_experiment.json"
REAL_CSV_PATH = DATA_DIR / "real_remote_budget_samples.csv"


def build_real_remote_budget_experiment() -> dict:
    payload = _load_json(REAL_JSON_PATH)
    if payload.get("check_only"):
        raise RuntimeError("真实远端实验尚未完成，请先运行完整实验而非 --check-only")
    samples = _load_samples(REAL_CSV_PATH)
    peak_sample = max(samples, key=lambda item: item["power_usage"])
    first_post = next(item for item in samples if item["phase"] == "post_action")
    action = payload["scheduler_run"]["budget_actions"][0]
    result = payload["scheduler_run"]["budget_results"][0]
    power_drop = round(peak_sample["power_usage"] - payload["summary"]["post_action"]["avg_power"], 2)
    total_drop = round(peak_sample["total_power"] - first_post["total_power"], 2)
    return {
        "host": payload["host"],
        "gpu_index": payload["gpu_index"],
        "workload_pid": payload["workload_pid"],
        "workload_log": payload["workload_log"],
        "original_power_limit": payload["original_power_limit"],
        "managed_power_limit": int(action["target"]["power_limit"]),
        "budget_limit": int(payload["scheduler_run"]["budget_limit"]),
        "power_alert_threshold": int(payload["alerts"][0]["threshold"]),
        "alert_message": payload["alerts"][0]["message"],
        "baseline": payload["summary"]["baseline"],
        "ramp": payload["summary"]["ramp"],
        "post_action": payload["summary"]["post_action"],
        "effective": bool(payload["summary"]["effective"]),
        "peak_sample": peak_sample,
        "first_post_sample": first_post,
        "power_drop_watts": power_drop,
        "power_drop_pct": round(power_drop / peak_sample["power_usage"] * 100, 1),
        "total_power_drop_watts": total_drop,
        "action_success": bool(result["success"]),
        "post_clean_ratio_pct": round(
            (payload["summary"]["post_action"]["sample_count"] - payload["summary"]["post_action"]["above_alert_samples"])
            / payload["summary"]["post_action"]["sample_count"] * 100,
            1,
        ),
        "samples": samples,
    }


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"缺少真实实验结果文件：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_samples(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"缺少真实实验采样文件：{path}")
    with path.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return [_normalize_row(row) for row in rows]


def _normalize_row(row: dict) -> dict:
    return {
        "timestamp": float(row["timestamp"]),
        "elapsed_s": float(row["elapsed_s"]),
        "phase": row["phase"],
        "gpu_index": int(row["gpu_index"]),
        "power_usage": float(row["power_usage"]),
        "power_limit": float(row["power_limit"]),
        "temperature": int(row["temperature"]),
        "gpu_utilization": int(row["gpu_utilization"]),
        "total_power": float(row["total_power"]),
        "above_power_alert": row["above_power_alert"] == "True",
    }
