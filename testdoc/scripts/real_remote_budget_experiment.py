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
from app.services.runtime_provider import RuntimeTarget
from app.services.scheduler import SchedulerEngine
from app.services.ssh_linux_provider import SshLinuxProvider
from real_remote_budget_experiment_common import (
    LOAD_WAIT_TIMEOUT_SECONDS,
    POST_ACTION_SAMPLES,
    POWER_ALERT_THRESHOLD,
    REMOTE_SCRIPT,
    SAMPLE_INTERVAL_SECONDS,
    build_remote_paths,
    compute_budget_limit,
    ensure_safe_gpu,
    shell_wrap,
    summarize_window,
    write_csv,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="真实远端功耗预算治理实验")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--sudo-password", default="")
    parser.add_argument("--gpu-index", type=int, default=3)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--output-json", default=str(ROOT / "testdoc" / "data" / "real_remote_budget_experiment.json"))
    parser.add_argument("--output-csv", default=str(ROOT / "testdoc" / "data" / "real_remote_budget_samples.csv"))
    return parser.parse_args()


def build_provider(args: argparse.Namespace) -> SshLinuxProvider:
    target = RuntimeTarget(
        provider_type="ssh_linux",
        label=f"remote-{args.host}",
        host=args.host,
        port=args.port,
        username=args.username,
        auth_type="password",
        sudo_enabled=True,
    )
    secret = {
        "password": args.password,
        "sudo_password": args.sudo_password or args.password,
    }
    return SshLinuxProvider(target, secret)
async def run_remote(provider: SshLinuxProvider, command: str, use_sudo: bool = False) -> str:
    result = await provider.executor.run(command, use_sudo=use_sudo, timeout=30.0)
    if result.code != 0:
        detail = result.stderr.strip() or result.stdout.strip() or command
        raise RuntimeError(detail)
    return result.stdout.strip()


async def deploy_workload_script(provider: SshLinuxProvider, script_path: str) -> None:
    command = shell_wrap(f"cat > {script_path} <<'PY'\n{REMOTE_SCRIPT}\nPY")
    await run_remote(provider, command)


async def discover_python(provider: SshLinuxProvider) -> str:
    command = shell_wrap(
        "source ~/.bashrc >/dev/null 2>&1; "
        "if [ -x \"$HOME/miniconda3/bin/python\" ]; then "
        "echo \"$HOME/miniconda3/bin/python\"; "
        "else command -v python || command -v python3; fi"
    )
    python_bin = await run_remote(provider, command)
    if not python_bin:
        raise RuntimeError("远端未找到可用 Python 解释器")
    return python_bin.splitlines()[0].strip()


async def start_workload(
    provider: SshLinuxProvider,
    gpu_index: int,
    python_bin: str,
) -> tuple[int, str, str]:
    script_path, log_path = build_remote_paths(gpu_index)
    await deploy_workload_script(provider, script_path)
    launch = (
        f"CUDA_VISIBLE_DEVICES={gpu_index} nohup {python_bin} {script_path} "
        f">{log_path} 2>&1 & echo $!"
    )
    pid_text = await run_remote(provider, shell_wrap(launch))
    return int(pid_text.strip()), script_path, log_path


async def stop_workload(provider: SshLinuxProvider, pid: int, script_path: str) -> None:
    await provider.terminate_task(pid)
    await run_remote(provider, shell_wrap(f"rm -f {script_path}"))


def sample_gpu(gpus: list[dict], gpu_index: int, phase: str, started_at: float) -> dict:
    target = next(gpu for gpu in gpus if int(gpu.get("index", -1)) == gpu_index)
    total_power = sum(float(item.get("power_usage", 0) or 0) for item in gpus)
    timestamp = time.time()
    return {
        "timestamp": round(timestamp, 3),
        "elapsed_s": round(timestamp - started_at, 2),
        "phase": phase,
        "gpu_index": gpu_index,
        "power_usage": round(float(target.get("power_usage", 0) or 0), 2),
        "power_limit": round(float(target.get("power_limit", 0) or 0), 2),
        "temperature": int(target.get("temperature", 0) or 0),
        "gpu_utilization": int(target.get("gpu_utilization", 0) or 0),
        "total_power": round(total_power, 2),
        "above_power_alert": float(target.get("power_usage", 0) or 0) >= POWER_ALERT_THRESHOLD,
    }


async def capture_sample(
    provider: SshLinuxProvider,
    store: DataStore,
    alert_engine: AlertEngine,
    gpu_index: int,
    phase: str,
    started_at: float,
) -> dict:
    gpus = await provider.get_all_gpus()
    sample = sample_gpu(gpus, gpu_index, phase, started_at)
    for gpu in gpus:
        gpu["timestamp"] = sample["timestamp"]
    await store.save_gpu_snapshot(gpus)
    alerts = alert_engine.check_all_gpus(gpus)
    if alerts:
        await store.save_alerts(alerts)
    return sample


async def wait_for_peak(
    provider: SshLinuxProvider,
    store: DataStore,
    alert_engine: AlertEngine,
    gpu_index: int,
    started_at: float,
) -> list[dict]:
    samples: list[dict] = []
    deadline = time.time() + LOAD_WAIT_TIMEOUT_SECONDS
    while time.time() < deadline:
        sample = await capture_sample(provider, store, alert_engine, gpu_index, "load_ramp", started_at)
        samples.append(sample)
        if sample["power_usage"] >= POWER_ALERT_THRESHOLD:
            return samples
        await asyncio.sleep(SAMPLE_INTERVAL_SECONDS)
    raise RuntimeError(f"GPU {gpu_index} 未在 {LOAD_WAIT_TIMEOUT_SECONDS}s 内达到 {POWER_ALERT_THRESHOLD}W")


async def collect_window(
    provider: SshLinuxProvider,
    store: DataStore,
    alert_engine: AlertEngine,
    gpu_index: int,
    phase: str,
    started_at: float,
    sample_count: int,
) -> list[dict]:
    samples: list[dict] = []
    for _ in range(sample_count):
        sample = await capture_sample(provider, store, alert_engine, gpu_index, phase, started_at)
        samples.append(sample)
        await asyncio.sleep(SAMPLE_INTERVAL_SECONDS)
    return samples


async def run_scheduler_once(
    provider: SshLinuxProvider,
    store: DataStore,
    gpu_index: int,
    target_pid: int,
) -> dict:
    scheduler = SchedulerEngine(provider, store, llm_service=None, import_context=None, budget_enabled=True)
    gpus = await provider.get_all_gpus()
    processes = await provider.get_processes()
    await store.track_processes(processes)
    await store.set_task_priority(target_pid, "deferrable")
    budget_limit = compute_budget_limit(sample_gpu(gpus, gpu_index, "pre_action", time.time()))
    scheduler.configure_budget(True, budget_limit)
    rule_actions = await scheduler.run_rules(gpus, processes)
    rule_results = await scheduler.execute_actions(rule_actions) if rule_actions else []
    budget_actions = await scheduler.run_budget_schedule(gpus, processes)
    budget_results = await scheduler.execute_actions(budget_actions) if budget_actions else []
    latest_gpus = await provider.get_all_gpus()
    return {
        "budget_limit": budget_limit,
        "rule_actions": rule_actions,
        "rule_results": rule_results,
        "budget_actions": budget_actions,
        "budget_results": budget_results,
        "budget_status": scheduler.get_budget_status(latest_gpus),
    }
async def run_experiment(args: argparse.Namespace) -> dict:
    provider = build_provider(args)
    store = DataStore(str(ROOT / "testdoc" / "data" / "real_remote_budget_store.db"))
    alert_engine = AlertEngine(power_threshold=POWER_ALERT_THRESHOLD)
    started_at = time.time()
    pid = 0
    original_limit = 0
    script_path = ""
    await store.init()
    try:
        health = await provider.health_check()
        if not health:
            raise RuntimeError("SSH provider 健康检查失败")
        gpus = await provider.get_all_gpus()
        target = ensure_safe_gpu(gpus, args.gpu_index)
        original_limit = int(round(float(target.get("power_limit", 0) or 0)))
        python_bin = await discover_python(provider)
        if args.check_only:
            return {
                "check_only": True,
                "host": args.host,
                "gpu": target,
                "python_bin": python_bin,
                "sudo_ready": provider.capabilities_snapshot()["sudo_ready"],
            }
        baseline = await collect_window(provider, store, alert_engine, args.gpu_index, "baseline", started_at, 4)
        pid, script_path, log_path = await start_workload(provider, args.gpu_index, python_bin)
        ramp = await wait_for_peak(provider, store, alert_engine, args.gpu_index, started_at)
        scheduler_run = await run_scheduler_once(provider, store, args.gpu_index, pid)
        post = await collect_window(provider, store, alert_engine, args.gpu_index, "post_action", started_at, POST_ACTION_SAMPLES)
        all_samples = baseline + ramp + post
        alerts = await store.get_alerts(limit=50, gpu_indexes=[args.gpu_index])
        summary = {
            "baseline": summarize_window(baseline),
            "ramp": summarize_window(ramp),
            "post_action": summarize_window(post),
            "effective": summarize_window(post)["avg_power"] < summarize_window(ramp)["peak_power"] - 40,
        }
        return {
            "check_only": False,
            "host": args.host,
            "gpu_index": args.gpu_index,
            "sudo_ready": provider.capabilities_snapshot()["sudo_ready"],
            "target_gpu_before": target,
            "original_power_limit": original_limit,
            "workload_pid": pid,
            "workload_log": log_path,
            "alerts": alerts,
            "scheduler_run": scheduler_run,
            "summary": summary,
            "samples": all_samples,
        }
    finally:
        if pid > 0:
            await stop_workload(provider, pid, script_path)
        if original_limit:
            await provider.set_power_limit(args.gpu_index, original_limit)
        await provider.close()
        await store.close()


def persist_outputs(result: dict, json_path: Path, csv_path: Path) -> None:
    samples = list(result.pop("samples", []))
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if samples:
        write_csv(csv_path, samples)


def main() -> None:
    args = parse_args()
    result = asyncio.run(run_experiment(args))
    json_path = Path(args.output_json)
    csv_path = Path(args.output_csv)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    persist_outputs(result, json_path, csv_path)
    print(json.dumps({"json": str(json_path), "csv": str(csv_path), "summary": result.get("summary", {})}, ensure_ascii=False))


if __name__ == "__main__":
    main()
