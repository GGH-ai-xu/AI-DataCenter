from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
SCRIPT_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from app.services.alert_engine import AlertEngine
from app.services.data_store import DataStore
from app.services.scheduler import SchedulerEngine
from real_remote_budget_experiment import (
    build_provider,
    discover_python,
    start_workload,
    stop_workload,
)
from real_remote_budget_experiment_common import (
    POST_ACTION_SAMPLES,
    POWER_ALERT_THRESHOLD,
    SAMPLE_INTERVAL_SECONDS,
    choose_governance_pair,
    compute_transition_latency,
    find_idle_gpu_candidates,
    summarize_role_window,
    write_csv,
)


DEFAULT_OUTPUT_JSON = ROOT / "testdoc" / "data" / "real_remote_dual_gpu_competition.json"
DEFAULT_OUTPUT_CSV = ROOT / "testdoc" / "data" / "real_remote_dual_gpu_competition_samples.csv"
DEFAULT_STORE_DB = ROOT / "testdoc" / "data" / "real_remote_dual_gpu_competition_store.db"
BASELINE_SAMPLE_COUNT = 4
LOAD_SAMPLE_LIMIT = 20


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="双 GPU 并发竞争治理实验")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--sudo-password", default="")
    parser.add_argument("--governance-gpu-index", type=int, default=-1)
    parser.add_argument("--control-gpu-index", type=int, default=-1)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-csv", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--store-db", default=str(DEFAULT_STORE_DB))
    return parser.parse_args()


def select_gpu_pair(args: argparse.Namespace, gpus: list[dict]) -> tuple[dict, dict]:
    if args.governance_gpu_index >= 0 and args.control_gpu_index >= 0:
        governance = _safe_gpu(gpus, args.governance_gpu_index)
        control = _safe_gpu(gpus, args.control_gpu_index)
        if governance["index"] == control["index"]:
            raise RuntimeError("治理 GPU 与对照 GPU 不能是同一张卡")
        return governance, control
    candidates = find_idle_gpu_candidates(gpus, minimum_count=len(gpus))
    matched = _matching_limit_pair(candidates)
    if matched is not None:
        return matched
    return choose_governance_pair(gpus)


def _safe_gpu(gpus: list[dict], gpu_index: int) -> dict:
    target = next((gpu for gpu in gpus if int(gpu.get("index", -1)) == gpu_index), None)
    if target is None:
        raise RuntimeError(f"GPU {gpu_index} 不存在")
    power_usage = float(target.get("power_usage", 0) or 0)
    utilization = int(target.get("gpu_utilization", 0) or 0)
    if power_usage > 60 or utilization > 10:
        raise RuntimeError(
            f"GPU {gpu_index} 非空闲状态，功耗 {power_usage}W，利用率 {utilization}%"
        )
    return target


def _matching_limit_pair(candidates: list[dict]) -> tuple[dict, dict] | None:
    grouped: dict[int, list[dict]] = {}
    for gpu in candidates:
        grouped.setdefault(int(round(float(gpu.get("power_limit", 0) or 0))), []).append(gpu)
    for power_limit in sorted(grouped.keys(), reverse=True):
        group = sorted(grouped[power_limit], key=lambda item: int(item.get("index", -1)))
        if len(group) >= 2:
            return group[0], group[1]
    return None


def _role_map(governance_gpu_index: int, control_gpu_index: int) -> dict[int, str]:
    return {
        governance_gpu_index: "governance",
        control_gpu_index: "control",
    }


def _role_sample(
    gpu: dict,
    *,
    role: str,
    phase: str,
    started_at: float,
    total_power: float,
) -> dict:
    timestamp = time.time()
    return {
        "timestamp": round(timestamp, 3),
        "elapsed_s": round(timestamp - started_at, 2),
        "phase": phase,
        "gpu_index": int(gpu.get("index", -1)),
        "gpu_role": role,
        "power_usage": round(float(gpu.get("power_usage", 0) or 0), 2),
        "power_limit": round(float(gpu.get("power_limit", 0) or 0), 2),
        "temperature": int(gpu.get("temperature", 0) or 0),
        "gpu_utilization": int(gpu.get("gpu_utilization", 0) or 0),
        "total_power": round(total_power, 2),
        "above_power_alert": float(gpu.get("power_usage", 0) or 0) >= POWER_ALERT_THRESHOLD,
    }


async def capture_role_samples(
    provider,
    store: DataStore,
    alert_engine: AlertEngine,
    role_map: dict[int, str],
    phase: str,
    started_at: float,
) -> list[dict]:
    gpus = await provider.get_all_gpus()
    total_power = sum(float(item.get("power_usage", 0) or 0) for item in gpus)
    timestamp = time.time()
    for gpu in gpus:
        gpu["timestamp"] = round(timestamp, 3)
    await store.save_gpu_snapshot(gpus)
    alerts = alert_engine.check_all_gpus(gpus)
    if alerts:
        await store.save_alerts(alerts)
    return [
        _role_sample(
            gpu,
            role=role_map[int(gpu.get("index", -1))],
            phase=phase,
            started_at=started_at,
            total_power=total_power,
        )
        for gpu in gpus
        if int(gpu.get("index", -1)) in role_map
    ]


async def collect_role_window(
    provider,
    store: DataStore,
    alert_engine: AlertEngine,
    role_map: dict[int, str],
    phase: str,
    started_at: float,
    sample_count: int,
) -> list[dict]:
    samples: list[dict] = []
    for _ in range(sample_count):
        samples.extend(
            await capture_role_samples(
                provider,
                store,
                alert_engine,
                role_map,
                phase,
                started_at,
            )
        )
        await asyncio.sleep(SAMPLE_INTERVAL_SECONDS)
    return samples


async def wait_for_dual_peak(
    provider,
    store: DataStore,
    alert_engine: AlertEngine,
    role_map: dict[int, str],
    started_at: float,
) -> list[dict]:
    samples: list[dict] = []
    governance_hit = False
    control_hit = False
    for _ in range(LOAD_SAMPLE_LIMIT):
        rows = await capture_role_samples(
            provider,
            store,
            alert_engine,
            role_map,
            "load_ramp",
            started_at,
        )
        samples.extend(rows)
        governance_hit = governance_hit or _role_above_threshold(rows, "governance")
        control_hit = control_hit or _role_above_threshold(rows, "control")
        if governance_hit and control_hit:
            return samples
        await asyncio.sleep(SAMPLE_INTERVAL_SECONDS)
    raise RuntimeError("两张 GPU 未在限定时间内同时进入高功耗区间")


def _role_above_threshold(rows: list[dict], role: str) -> bool:
    return any(
        str(item.get("gpu_role") or "") == role
        and bool(item.get("above_power_alert", False))
        for item in rows
    )


async def run_targeted_budget_schedule(
    provider,
    store: DataStore,
    governance_gpu_index: int,
    control_gpu_index: int,
    governance_pid: int,
    control_pid: int,
) -> dict:
    scheduler = SchedulerEngine(
        provider,
        store,
        llm_service=None,
        import_context=None,
        budget_enabled=True,
    )
    gpus = await provider.get_all_gpus()
    processes = await provider.get_processes()
    await store.track_processes(processes)
    await store.set_task_priority(governance_pid, "deferrable")
    await store.set_task_priority(control_pid, "urgent")
    enriched_processes = await scheduler._attach_priorities(processes)
    profiles = scheduler._build_budget_profiles(gpus, enriched_processes)
    governance_profile = next(
        (
            item
            for item in profiles
            if int(item.get("index", -1)) == governance_gpu_index
        ),
        None,
    )
    if governance_profile is None:
        raise RuntimeError("未找到治理 GPU 的预算画像")
    suggested_limit = scheduler._suggest_budget_limit(governance_profile)
    if suggested_limit is None:
        raise RuntimeError("治理 GPU 不满足预算压缩条件，无法形成针对性治理动作")
    estimated_saving = int(round(governance_profile["power_usage"] - suggested_limit))
    if estimated_saving < 20:
        raise RuntimeError("治理 GPU 预估节流收益过小，无法形成有效对照")
    current_total = sum(float(gpu.get("power_usage", 0) or 0) for gpu in gpus)
    target_excess = max(20, estimated_saving - 5)
    budget_limit = int(round(current_total - target_excess))
    scheduler.configure_budget(True, budget_limit)
    budget_actions = await scheduler.run_budget_schedule(gpus, processes)
    governance_actions = [
        item
        for item in budget_actions
        if int(item.get("target", {}).get("gpu_index", -1)) == governance_gpu_index
    ]
    control_actions = [
        item
        for item in budget_actions
        if int(item.get("target", {}).get("gpu_index", -1)) == control_gpu_index
    ]
    invalid_actions = [
        item
        for item in budget_actions
        if item.get("action") != "set_power_limit"
    ]
    if not governance_actions:
        raise RuntimeError("预算调度未选中治理 GPU，实验不成立")
    if control_actions:
        raise RuntimeError("预算调度同时选中了对照 GPU，实验不成立")
    if invalid_actions:
        raise RuntimeError("预算调度产生了非 set_power_limit 动作，实验不成立")
    budget_results = await scheduler.execute_actions(governance_actions)
    latest_gpus = await provider.get_all_gpus()
    governance_result = governance_actions[0]
    return {
        "current_total_power": round(current_total, 2),
        "budget_limit": budget_limit,
        "governance_gpu_index": governance_gpu_index,
        "control_gpu_index": control_gpu_index,
        "governance_priority": "deferrable",
        "control_priority": "urgent",
        "suggested_limit": suggested_limit,
        "estimated_saving": estimated_saving,
        "budget_actions": governance_actions,
        "budget_results": budget_results,
        "budget_status": scheduler.get_budget_status(latest_gpus),
        "selected_action": governance_result,
    }


def build_summary(samples: list[dict], scheduler_run: dict) -> dict:
    governance_baseline = summarize_role_window(samples, "governance", "baseline")
    governance_ramp = summarize_role_window(samples, "governance", "load_ramp")
    governance_post = summarize_role_window(samples, "governance", "post_action")
    control_baseline = summarize_role_window(samples, "control", "baseline")
    control_ramp = summarize_role_window(samples, "control", "load_ramp")
    control_post = summarize_role_window(samples, "control", "post_action")
    governance_latency = compute_transition_latency(
        samples,
        "governance",
        POWER_ALERT_THRESHOLD,
    )
    control_latency = compute_transition_latency(
        samples,
        "control",
        POWER_ALERT_THRESHOLD,
    )
    governance_clean_ratio = _clean_ratio(governance_post)
    control_clean_ratio = _clean_ratio(control_post)
    total_power_drop = _post_total_drop(samples)
    return {
        "governance": {
            "baseline": governance_baseline,
            "ramp": governance_ramp,
            "post_action": governance_post,
        },
        "control": {
            "baseline": control_baseline,
            "ramp": control_ramp,
            "post_action": control_post,
        },
        "contrast": {
            "governance_drop_from_peak_w": round(
                governance_ramp["peak_power"] - governance_post["avg_power"],
                2,
            ),
            "control_drop_from_peak_w": round(
                control_ramp["peak_power"] - control_post["avg_power"],
                2,
            ),
            "post_avg_power_gap_w": round(
                control_post["avg_power"] - governance_post["avg_power"],
                2,
            ),
            "post_avg_temp_gap_c": round(
                control_post["avg_temperature"] - governance_post["avg_temperature"],
                2,
            ),
            "governance_clean_ratio_pct": governance_clean_ratio,
            "control_clean_ratio_pct": control_clean_ratio,
            "total_power_drop_after_action_w": total_power_drop,
        },
        "latency": {
            "governance": governance_latency,
            "control": control_latency,
        },
        "effective": bool(
            governance_clean_ratio == 100.0
            and control_clean_ratio < 100.0
            and governance_post["avg_power"] < control_post["avg_power"] - 30
        ),
        "budget_limit": scheduler_run["budget_limit"],
    }


def _clean_ratio(summary: dict) -> float:
    sample_count = int(summary.get("sample_count", 0) or 0)
    if sample_count <= 0:
        return 0.0
    clean = sample_count - int(summary.get("above_alert_samples", 0) or 0)
    return round(clean / sample_count * 100.0, 1)


def _post_total_drop(samples: list[dict]) -> float:
    ramp = [
        item["total_power"]
        for item in samples
        if str(item.get("gpu_role") or "") == "governance"
        and str(item.get("phase") or "") == "load_ramp"
    ]
    post = [
        item["total_power"]
        for item in samples
        if str(item.get("gpu_role") or "") == "governance"
        and str(item.get("phase") or "") == "post_action"
    ]
    if not ramp or not post:
        return 0.0
    return round(max(ramp) - min(post), 2)


async def run_experiment(args: argparse.Namespace) -> dict:
    provider = build_provider(args)
    store = DataStore(str(args.store_db))
    alert_engine = AlertEngine(power_threshold=POWER_ALERT_THRESHOLD)
    started_at = time.time()
    governance_pid = 0
    control_pid = 0
    governance_script = ""
    control_script = ""
    governance_gpu_index = -1
    control_gpu_index = -1
    original_governance_limit = 0
    original_control_limit = 0
    await store.init()
    try:
        health = await provider.health_check()
        if not health:
            raise RuntimeError("SSH provider 健康检查失败")
        gpus = await provider.get_all_gpus()
        governance_gpu, control_gpu = select_gpu_pair(args, gpus)
        governance_gpu_index = int(governance_gpu.get("index", -1))
        control_gpu_index = int(control_gpu.get("index", -1))
        original_governance_limit = int(round(float(governance_gpu.get("power_limit", 0) or 0)))
        original_control_limit = int(round(float(control_gpu.get("power_limit", 0) or 0)))
        if args.check_only:
            return {
                "check_only": True,
                "host": args.host,
                "governance_gpu": governance_gpu,
                "control_gpu": control_gpu,
                "idle_candidates": gpus,
                "sudo_ready": provider.capabilities_snapshot()["sudo_ready"],
            }
        python_bin = await discover_python(provider)
        role_map = _role_map(governance_gpu_index, control_gpu_index)
        baseline = await collect_role_window(
            provider,
            store,
            alert_engine,
            role_map,
            "baseline",
            started_at,
            BASELINE_SAMPLE_COUNT,
        )
        governance_pid, governance_script, governance_log = await start_workload(
            provider,
            governance_gpu_index,
            python_bin,
        )
        control_pid, control_script, control_log = await start_workload(
            provider,
            control_gpu_index,
            python_bin,
        )
        ramp = await wait_for_dual_peak(
            provider,
            store,
            alert_engine,
            role_map,
            started_at,
        )
        scheduler_run = await run_targeted_budget_schedule(
            provider,
            store,
            governance_gpu_index,
            control_gpu_index,
            governance_pid,
            control_pid,
        )
        post = await collect_role_window(
            provider,
            store,
            alert_engine,
            role_map,
            "post_action",
            started_at,
            POST_ACTION_SAMPLES,
        )
        all_samples = baseline + ramp + post
        alerts = await store.get_alerts(
            limit=100,
            gpu_indexes=[governance_gpu_index, control_gpu_index],
        )
        return {
            "check_only": False,
            "host": args.host,
            "sudo_ready": provider.capabilities_snapshot()["sudo_ready"],
            "governance_gpu_index": governance_gpu_index,
            "control_gpu_index": control_gpu_index,
            "governance_original_power_limit": original_governance_limit,
            "control_original_power_limit": original_control_limit,
            "governance_workload_pid": governance_pid,
            "control_workload_pid": control_pid,
            "governance_workload_log": governance_log,
            "control_workload_log": control_log,
            "alerts": alerts,
            "scheduler_run": scheduler_run,
            "summary": build_summary(all_samples, scheduler_run),
            "samples": all_samples,
        }
    finally:
        if governance_pid > 0:
            await stop_workload(provider, governance_pid, governance_script)
        if control_pid > 0:
            await stop_workload(provider, control_pid, control_script)
        if governance_gpu_index >= 0 and original_governance_limit:
            await provider.set_power_limit(
                governance_gpu_index,
                original_governance_limit,
            )
        if control_gpu_index >= 0 and original_control_limit:
            await provider.set_power_limit(
                control_gpu_index,
                original_control_limit,
            )
        await provider.close()
        await store.close()


def persist_outputs(result: dict, json_path: Path, csv_path: Path) -> None:
    json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    samples = list(result.get("samples", []))
    if samples:
        write_csv(csv_path, samples)


def main() -> None:
    args = parse_args()
    result = asyncio.run(run_experiment(args))
    json_path = Path(args.output_json)
    csv_path = Path(args.output_csv)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    persist_outputs(result, json_path, csv_path)
    print(
        json.dumps(
            {
                "json": str(json_path),
                "csv": str(csv_path),
                "summary": result.get("summary", {}),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
