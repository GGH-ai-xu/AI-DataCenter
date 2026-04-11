from __future__ import annotations

import asyncio
import json
import shlex
import time

from real_remote_budget_experiment import run_remote
from real_remote_budget_experiment_common import find_idle_gpu_candidates, shell_wrap


RUNTIME_BASE_URL = "http://127.0.0.1:8001"
SAMPLE_INTERVAL_SECONDS = 2.0
PAUSE_SAMPLE_COUNT = 3
POST_RESTORE_SAMPLE_COUNT = 4
AGENT_LOG_PATH = "/tmp/aidc_server_agent.log"
WORKLOAD_SCRIPT = """import json, os, time
from pathlib import Path
import torch

control_dir = Path(os.environ["AIDC_CONTROL_DIR"])
artifact_root = Path(os.environ["AIDC_ARTIFACT_ROOT"])
artifact_root.mkdir(parents=True, exist_ok=True)
restore_from = os.environ.get("AIDC_RESTORE_FROM", "")
visible_gpu = os.environ.get("CUDA_VISIBLE_DEVICES", "")
state_path = artifact_root / "progress.json"
log_path = artifact_root / "progress.log"
req_path = control_dir / "checkpoint-request.json"
res_path = control_dir / "checkpoint-result.json"
step = 0
restored = False
if restore_from:
    payload = json.loads(Path(restore_from).read_text(encoding="utf-8"))
    step = int(payload.get("step", 0))
    restored = True
torch.backends.cuda.matmul.allow_tf32 = True
torch.set_float32_matmul_precision("high")
device = torch.device("cuda")
size = 16384
a = torch.randn((size, size), device=device, dtype=torch.float16)
b = torch.randn((size, size), device=device, dtype=torch.float16)
out = torch.empty((size, size), device=device, dtype=torch.float16)
def write_state(event):
    payload = {"timestamp": round(time.time(), 3), "step": int(step), "visible_gpu": visible_gpu, "event": event, "restored": restored, "restore_from": restore_from}
    state_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\\n")
write_state("restored" if restored else "started")
deadline = time.time() + 240
while time.time() < deadline:
    torch.matmul(a, b, out=out)
    torch.cuda.synchronize()
    step += 1
    if step % 2 == 0:
        write_state("running")
    if req_path.exists():
        request = json.loads(req_path.read_text(encoding="utf-8"))
        manifest_path = artifact_root / f"{request['checkpoint_id']}.json"
        manifest = {"checkpoint_id": request["checkpoint_id"], "step": int(step), "visible_gpu": visible_gpu, "saved_at": round(time.time(), 3)}
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        res_path.write_text(json.dumps({"checkpoint_id": request["checkpoint_id"], "status": "ready", "manifest_path": str(manifest_path), "artifact_paths": [str(state_path), str(log_path)], "completed_at": round(time.time(), 3)}, ensure_ascii=False), encoding="utf-8")
        write_state("checkpoint_ready")
        while True:
            time.sleep(1)
"""


def build_remote_script_path(source_gpu_index: int) -> str:
    return f"/tmp/aidc_checkpoint_restore_gpu{source_gpu_index}_{int(time.time())}.py"


def select_gpu_pair(args, gpus: list[dict]) -> tuple[int, int]:
    if args.source_gpu_index >= 0 and args.target_gpu_index >= 0:
        return args.source_gpu_index, args.target_gpu_index
    candidates = find_idle_gpu_candidates(gpus, minimum_count=len(gpus))
    if len(candidates) < 2:
        raise RuntimeError("空闲 GPU 少于 2 张，无法执行检查点恢复实验")
    return int(candidates[0]["index"]), int(candidates[1]["index"])


async def runtime_call(provider, method: str, path: str, payload: dict | None = None) -> dict:
    curl = f"curl -sS -X {method} {shlex.quote(RUNTIME_BASE_URL + path)}"
    if payload is not None:
        curl += " -H 'Content-Type: application/json' --data " + shlex.quote(
            json.dumps(payload, ensure_ascii=False)
        )
    output = await run_remote(provider, shell_wrap(curl))
    return json.loads(output or "{}")


async def try_runtime_health(provider) -> dict | None:
    try:
        return await runtime_call(provider, "GET", "/api/health")
    except Exception:
        return None


async def ensure_remote_agent(provider, python_bin: str) -> dict:
    health = await try_runtime_health(provider)
    if health:
        return {"started": False, "health": health, "log_path": AGENT_LOG_PATH}
    main_path = await run_remote(
        provider,
        shell_wrap("find ~ -maxdepth 5 -path '*/server-agent/main.py' 2>/dev/null | head -n 1"),
    )
    if not main_path:
        raise RuntimeError("远端未找到 server-agent/main.py，无法启动 runtime agent")
    agent_dir = main_path.strip().rsplit("/", 1)[0]
    pid_text = await run_remote(
        provider,
        shell_wrap(
            f"cd {shlex.quote(agent_dir)} && nohup {shlex.quote(python_bin)} main.py >{AGENT_LOG_PATH} 2>&1 & echo $!"
        ),
    )
    for _ in range(12):
        await asyncio.sleep(1)
        health = await try_runtime_health(provider)
        if health:
            return {
                "started": True,
                "health": health,
                "pid": int(pid_text.strip() or 0),
                "agent_dir": agent_dir,
                "log_path": AGENT_LOG_PATH,
            }
    log_tail = await run_remote(provider, shell_wrap(f"tail -n 40 {AGENT_LOG_PATH} || true"))
    raise RuntimeError(f"远端 server-agent 启动失败：{log_tail.strip() or 'health unavailable'}")


async def deploy_workload_script(provider, script_path: str) -> None:
    command = shell_wrap(f"cat > {script_path} <<'PY'\n{WORKLOAD_SCRIPT}\nPY")
    await run_remote(provider, command)


async def read_json_file(provider, path: str) -> dict:
    output = await run_remote(provider, shell_wrap(f"cat {shlex.quote(path)}"))
    return json.loads(output or "{}")


async def capture_sample(provider, source_gpu: int, target_gpu: int, phase: str, started_at: float) -> dict:
    gpus = await provider.get_all_gpus()
    processes = await provider.get_processes()
    gpu_map = {int(item["index"]): item for item in gpus}
    watched = [item for item in processes if int(item.get("gpu_index", -1)) in {source_gpu, target_gpu}]
    now = time.time()
    return {
        "timestamp": round(now, 3),
        "elapsed_s": round(now - started_at, 2),
        "phase": phase,
        "source_gpu_index": source_gpu,
        "target_gpu_index": target_gpu,
        "source_power_w": round(float(gpu_map[source_gpu].get("power_usage", 0) or 0), 2),
        "target_power_w": round(float(gpu_map[target_gpu].get("power_usage", 0) or 0), 2),
        "source_util": int(gpu_map[source_gpu].get("gpu_utilization", 0) or 0),
        "target_util": int(gpu_map[target_gpu].get("gpu_utilization", 0) or 0),
        "source_process_count": sum(1 for item in watched if int(item.get("gpu_index", -1)) == source_gpu),
        "target_process_count": sum(1 for item in watched if int(item.get("gpu_index", -1)) == target_gpu),
    }


async def wait_for_progress(provider, progress_path: str, minimum_step: int, timeout_seconds: float) -> dict:
    deadline = time.time() + timeout_seconds
    latest = {}
    last_error = ""
    while time.time() < deadline:
        try:
            latest = await read_json_file(provider, progress_path)
        except Exception as exc:
            last_error = str(exc)
            await asyncio.sleep(1)
            continue
        if int(latest.get("step", 0) or 0) >= minimum_step:
            return latest
        await asyncio.sleep(1)
    if last_error:
        raise RuntimeError(f"进度文件未就绪：{last_error}")
    raise RuntimeError(f"进度未在 {timeout_seconds}s 内达到 {minimum_step}")


async def wait_for_checkpoint_ready(provider, job_handle: str, timeout_seconds: float) -> dict:
    deadline = time.time() + timeout_seconds
    latest = {}
    while time.time() < deadline:
        latest = await runtime_call(provider, "GET", f"/api/runtime/jobs/{job_handle}/checkpoint")
        if str(latest.get("checkpoint_state") or "") == "checkpoint_ready":
            return latest
        await asyncio.sleep(1)
    raise RuntimeError("检查点在限定时间内未 ready")
