from __future__ import annotations

import argparse
import asyncio
import json
import shlex
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

from real_remote_budget_experiment import build_provider, discover_python, run_remote
from real_remote_budget_experiment_common import shell_wrap, write_csv
from real_remote_checkpoint_restore_common import (
    PAUSE_SAMPLE_COUNT,
    POST_RESTORE_SAMPLE_COUNT,
    SAMPLE_INTERVAL_SECONDS,
    build_remote_script_path,
    capture_sample,
    deploy_workload_script,
    read_json_file,
    select_gpu_pair,
    wait_for_progress,
)


DEFAULT_JSON = ROOT / "testdoc" / "data" / "real_remote_checkpoint_restore_experiment.json"
DEFAULT_CSV = ROOT / "testdoc" / "data" / "real_remote_checkpoint_restore_samples.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="真实远端检查点恢复实验（SSH 路径）")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--sudo-password", default="")
    parser.add_argument("--source-gpu-index", type=int, default=-1)
    parser.add_argument("--target-gpu-index", type=int, default=-1)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--output-json", default=str(DEFAULT_JSON))
    parser.add_argument("--output-csv", default=str(DEFAULT_CSV))
    return parser.parse_args()


def build_runtime_paths(handle: str) -> dict:
    root = f"/tmp/aidc_ssh_{handle}"
    return {
        "root": root,
        "control_dir": f"{root}/control",
        "artifact_root": f"{root}/artifacts",
        "progress_path": f"{root}/artifacts/progress.json",
        "checkpoint_request_path": f"{root}/control/checkpoint-request.json",
        "checkpoint_result_path": f"{root}/control/checkpoint-result.json",
        "log_path": f"{root}/run.log",
    }


def build_summary(result: dict) -> dict:
    paused = [item for item in result["samples"] if item["phase"] == "paused_window"]
    restored = [item for item in result["samples"] if item["phase"] == "restored_window"]
    checkpoint = result["checkpoint"]
    return {
        "source_gpu_index": result["source_gpu_index"],
        "target_gpu_index": result["target_gpu_index"],
        "pause_freeze_delta_steps": result["pause_state_after"]["step"] - result["pause_state_before"]["step"],
        "resume_recovery_delta_steps": result["resume_state_after"]["step"] - result["pause_state_after"]["step"],
        "checkpoint_step": checkpoint["manifest"]["step"],
        "restored_initial_step": result["restore_state_initial"]["step"],
        "restored_final_step": result["restore_state_final"]["step"],
        "progress_continued": result["restore_state_initial"]["step"] >= checkpoint["manifest"]["step"],
        "source_paused_avg_power_w": round(sum(item["source_power_w"] for item in paused) / max(len(paused), 1), 2),
        "target_restored_avg_power_w": round(sum(item["target_power_w"] for item in restored) / max(len(restored), 1), 2),
        "switch_latency_s": round(result["restore_started_at"] - checkpoint["ready_elapsed_s"], 2),
    }


async def write_remote_json(provider, path: str, payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    await run_remote(provider, shell_wrap(f"cat > {shlex.quote(path)} <<'JSON'\n{text}\nJSON"))


async def wait_for_checkpoint_file(provider, path: str, timeout_seconds: float) -> dict:
    deadline = time.time() + timeout_seconds
    latest = {}
    last_error = ""
    while time.time() < deadline:
        try:
            latest = await read_json_file(provider, path)
        except Exception as exc:
            last_error = str(exc)
            await asyncio.sleep(1)
            continue
        if str(latest.get("status") or "") == "ready":
            return latest
        await asyncio.sleep(1)
    if last_error:
        raise RuntimeError(f"检查点结果文件未就绪：{last_error}")
    raise RuntimeError("检查点结果文件在限定时间内未 ready")


async def probe_environment(provider, args: argparse.Namespace) -> tuple[int, int, str]:
    await provider.health_check()
    gpus = await provider.get_all_gpus()
    source_gpu, target_gpu = select_gpu_pair(args, gpus)
    python_bin = await discover_python(provider)
    return source_gpu, target_gpu, python_bin


async def launch_workload(provider, python_bin: str, script_path: str, gpu_index: int, handle: str, restore_from: str = "") -> dict:
    paths = build_runtime_paths(handle)
    await run_remote(provider, shell_wrap(f"mkdir -p {paths['control_dir']} {paths['artifact_root']}"))
    env = [
        f"CUDA_VISIBLE_DEVICES={gpu_index}",
        f"AIDC_CONTROL_DIR={paths['control_dir']}",
        f"AIDC_ARTIFACT_ROOT={paths['artifact_root']}",
    ]
    if restore_from:
        env.append(f"AIDC_RESTORE_FROM={restore_from}")
    launch = " ".join(env) + f" nohup {python_bin} {script_path} >{paths['log_path']} 2>&1 & echo $!"
    pid_text = await run_remote(provider, shell_wrap(launch))
    return {**paths, "pid": int(pid_text.strip() or 0), "gpu_index": gpu_index}


async def start_source_job(provider, source_gpu: int, python_bin: str) -> tuple[str, dict]:
    script_path = build_remote_script_path(source_gpu)
    await deploy_workload_script(provider, script_path)
    runtime = await launch_workload(provider, python_bin, script_path, source_gpu, "job-source")
    return script_path, runtime


async def run_pause_resume_phase(provider, source_gpu: int, target_gpu: int, started_at: float, source_runtime: dict) -> dict:
    running_state = await wait_for_progress(provider, source_runtime["progress_path"], 6, 60)
    samples = [await capture_sample(provider, source_gpu, target_gpu, "source_running", started_at)]
    paused_runtime = await provider.pause_task(source_runtime["pid"])
    await asyncio.sleep(4)
    pause_after = await read_json_file(provider, source_runtime["progress_path"])
    for _ in range(PAUSE_SAMPLE_COUNT):
        samples.append(await capture_sample(provider, source_gpu, target_gpu, "paused_window", started_at))
        await asyncio.sleep(SAMPLE_INTERVAL_SECONDS)
    resumed_runtime = await provider.resume_task(source_runtime["pid"])
    resume_after = await wait_for_progress(
        provider,
        source_runtime["progress_path"],
        int(pause_after["step"]) + 4,
        40,
    )
    samples.append(await capture_sample(provider, source_gpu, target_gpu, "source_resumed", started_at))
    return {
        "samples": samples,
        "paused_runtime": paused_runtime,
        "resumed_runtime": resumed_runtime,
        "pause_state_before": running_state,
        "pause_state_after": pause_after,
        "resume_state_after": resume_after,
    }


async def run_restore_phase(provider, source_gpu: int, target_gpu: int, started_at: float, source_runtime: dict, python_bin: str, script_path: str) -> dict:
    checkpoint_request = {
        "checkpoint_id": f"ckpt-{int(time.time())}",
        "artifact_root": source_runtime["artifact_root"],
        "timeout_seconds": 30,
        "requested_at": round(time.time(), 3),
    }
    await write_remote_json(provider, source_runtime["checkpoint_request_path"], checkpoint_request)
    checkpoint_status = await wait_for_checkpoint_file(provider, source_runtime["checkpoint_result_path"], 40)
    checkpoint_manifest = await read_json_file(provider, checkpoint_status["manifest_path"])
    ready_elapsed_s = round(time.time() - started_at, 2)
    samples = [await capture_sample(provider, source_gpu, target_gpu, "checkpoint_ready", started_at)]
    await provider.terminate_task(source_runtime["pid"])
    restore_started_at = round(time.time() - started_at, 2)
    restore_runtime = await launch_workload(
        provider,
        python_bin,
        script_path,
        target_gpu,
        "job-restore",
        checkpoint_status["manifest_path"],
    )
    restore_initial = await wait_for_progress(provider, restore_runtime["progress_path"], int(checkpoint_manifest["step"]), 40)
    restore_final = await wait_for_progress(provider, restore_runtime["progress_path"], int(restore_initial["step"]) + 4, 50)
    for _ in range(POST_RESTORE_SAMPLE_COUNT):
        samples.append(await capture_sample(provider, source_gpu, target_gpu, "restored_window", started_at))
        await asyncio.sleep(SAMPLE_INTERVAL_SECONDS)
    return {
        "samples": samples,
        "checkpoint_request": checkpoint_request,
        "checkpoint": {"status": checkpoint_status, "manifest": checkpoint_manifest, "ready_elapsed_s": ready_elapsed_s},
        "restore_runtime": restore_runtime,
        "restore_state_initial": restore_initial,
        "restore_state_final": restore_final,
        "restore_started_at": restore_started_at,
    }


async def cleanup_runtime(provider, script_path: str, runtimes: tuple[dict, ...], do_jobs: bool) -> None:
    if do_jobs:
        for runtime in runtimes:
            if not runtime:
                continue
            try:
                if int(runtime.get("pid", 0) or 0) > 0:
                    await provider.terminate_task(int(runtime["pid"]))
            except Exception:
                pass
            try:
                await run_remote(provider, shell_wrap(f"rm -rf {runtime['root']}"))
            except Exception:
                pass
    if script_path:
        try:
            await run_remote(provider, shell_wrap(f"rm -f {script_path}"))
        except Exception:
            pass
    await provider.close()


async def run_experiment(args: argparse.Namespace) -> dict:
    provider = build_provider(args)
    started_at = time.time()
    script_path = ""
    source_runtime: dict = {}
    restore_runtime: dict = {}
    try:
        source_gpu, target_gpu, python_bin = await probe_environment(provider, args)
        if args.check_only:
            return {"check_only": True, "source_gpu_index": source_gpu, "target_gpu_index": target_gpu, "execution_path": "ssh_provider"}
        script_path, source_runtime = await start_source_job(provider, source_gpu, python_bin)
        pause_phase = await run_pause_resume_phase(provider, source_gpu, target_gpu, started_at, source_runtime)
        restore_phase = await run_restore_phase(provider, source_gpu, target_gpu, started_at, source_runtime, python_bin, script_path)
        restore_runtime = restore_phase["restore_runtime"]
        return {
            "check_only": False,
            "host": args.host,
            "source_gpu_index": source_gpu,
            "target_gpu_index": target_gpu,
            "execution_path": "ssh_provider",
            "source_runtime": source_runtime,
            **pause_phase,
            **restore_phase,
            "samples": pause_phase["samples"] + restore_phase["samples"],
        }
    finally:
        await cleanup_runtime(provider, script_path, (source_runtime, restore_runtime), not args.check_only)


def persist_outputs(result: dict, json_path: Path, csv_path: Path) -> None:
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if result.get("samples"):
        write_csv(csv_path, result["samples"])


def main() -> None:
    args = parse_args()
    result = asyncio.run(run_experiment(args))
    if not args.check_only:
        result["summary"] = build_summary(result)
    json_path = Path(args.output_json)
    csv_path = Path(args.output_csv)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    persist_outputs(result, json_path, csv_path)
    print(json.dumps({"json": str(json_path), "csv": str(csv_path), "summary": result.get("summary", {})}, ensure_ascii=False))


if __name__ == "__main__":
    main()
