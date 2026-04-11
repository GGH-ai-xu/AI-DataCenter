"""GPU服务器Agent - FastAPI服务入口

部署在GPU服务器上，提供：
- GPU实时状态采集API
- 系统资源监控API
- GPU进程列表API
- 功耗控制API
- 任务暂停/恢复/终止API
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from collectors.gpu_monitor import gpu_monitor
from collectors.system_monitor import get_system_info, get_system_detail
from collectors.task_monitor import get_cached_gpu_processes
from collectors.training_monitor import get_training_logs
from controllers.power_control import set_power_limit
from controllers.task_control import pause_task, resume_task, terminate_task
from config import HOST, PORT, POWER_LIMIT_MIN, POWER_LIMIT_MAX
from job_runtime import JobRuntime
from runtime_store import RuntimeStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

NO_LOCAL_GPU_HINT = "若当前机器不是 NVIDIA 主机，或当前只使用 SSH Linux / 远程 Agent，可忽略此提示。"


def build_agent_startup_message() -> tuple[int, str]:
    if gpu_monitor.device_count > 0:
        return logging.INFO, f"Agent启动，检测到 {gpu_monitor.device_count} 张GPU"

    issue = gpu_monitor.startup_issue or "当前未检测到可采集的真实 GPU"
    return (
        logging.WARNING,
        f"Agent启动，但当前未检测到可采集的真实 GPU: {issue} {NO_LOCAL_GPU_HINT}",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    runtime_store.reset()
    gpu_monitor.init()
    level, message = build_agent_startup_message()
    logger.log(level, message)
    yield
    job_runtime.shutdown()
    gpu_monitor.shutdown()
    logger.info("Agent已关闭")


app = FastAPI(title="GPU Server Agent", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== 数据模型 ==========

class PowerLimitRequest(BaseModel):
    gpu_index: int = Field(ge=0, description="GPU索引")
    power_limit: int = Field(
        ge=POWER_LIMIT_MIN, le=POWER_LIMIT_MAX,
        description=f"目标功耗上限（{POWER_LIMIT_MIN}-{POWER_LIMIT_MAX}W）"
    )


class TaskActionRequest(BaseModel):
    pid: int = Field(gt=0, description="进程ID")


class RuntimeReservationRequest(BaseModel):
    reservation_id: str = Field(min_length=1, max_length=120)
    job_id: str = Field(min_length=1, max_length=120)
    gpu_indexes: list[int] = Field(default_factory=list)
    cpu_cores: list[int] = Field(default_factory=list)


class RuntimeJobLaunchRequest(BaseModel):
    job_handle: str = Field(min_length=1, max_length=120)
    job_id: str = Field(min_length=1, max_length=120)
    reservation_id: str = Field(min_length=1, max_length=120)
    command: list[str] = Field(min_length=1)
    env: dict[str, str] = Field(default_factory=dict)
    working_dir: str | None = Field(default=None, max_length=500)
    task_kind: str = Field(default="batch_compute", max_length=80)
    lifecycle_kind: str = Field(default="batch", max_length=40)
    service_ports: list[int] = Field(default_factory=list)
    checkpoint_policy: str = Field(default="none", max_length=40)
    runtime_profile: dict = Field(default_factory=dict)


class RuntimeCheckpointRequest(BaseModel):
    checkpoint_id: str = Field(min_length=1, max_length=120)
    timeout_seconds: int = Field(default=30, ge=1, le=3600)
    reason: str = Field(default="", max_length=500)


class RuntimeJobRestoreRequest(BaseModel):
    job_handle: str = Field(min_length=1, max_length=120)
    job_id: str = Field(min_length=1, max_length=120)
    reservation_id: str = Field(min_length=1, max_length=120)
    checkpoint_id: str = Field(min_length=1, max_length=120)
    manifest_path: str = Field(min_length=1, max_length=500)
    command: list[str] = Field(min_length=1)
    env: dict[str, str] = Field(default_factory=dict)
    working_dir: str | None = Field(default=None, max_length=500)
    task_kind: str = Field(default="batch_compute", max_length=80)
    lifecycle_kind: str = Field(default="batch", max_length=40)
    service_ports: list[int] = Field(default_factory=list)
    checkpoint_policy: str = Field(default="app_managed", max_length=40)
    runtime_profile: dict = Field(default_factory=dict)


runtime_store = RuntimeStore()
job_runtime = JobRuntime(runtime_store)


# ========== API路由 ==========

@app.get("/api/health")
def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "gpu_count": gpu_monitor.device_count,
    }


@app.get("/api/gpus")
def get_all_gpus():
    """获取所有GPU实时状态"""
    return {"gpus": gpu_monitor.get_all_gpus()}


@app.get("/api/gpus/{index}")
def get_gpu(index: int):
    """获取单张GPU状态"""
    info = gpu_monitor.get_gpu_info(index)
    if info is None:
        raise HTTPException(status_code=404, detail=f"GPU {index} 不存在")
    return info


@app.get("/api/system")
def get_system():
    """获取系统资源信息（基础）"""
    return get_system_info()


@app.get("/api/system/detail")
def get_system_full():
    """获取完整系统资源信息（含磁盘、网络、每核CPU）"""
    return get_system_detail()


@app.get("/api/processes")
def get_processes():
    """获取所有GPU上的进程列表"""
    procs = get_cached_gpu_processes(gpu_monitor.device_count)
    return {"processes": procs}


@app.get("/api/training/logs")
def get_training():
    """获取GPU训练进程的日志和指标"""
    procs = get_cached_gpu_processes(gpu_monitor.device_count)
    logs = get_training_logs(procs)
    return {"training": logs}


@app.post("/api/power-limit")
def api_set_power_limit(req: PowerLimitRequest):
    """设置GPU功耗上限"""
    if req.gpu_index >= gpu_monitor.device_count:
        raise HTTPException(status_code=404, detail=f"GPU {req.gpu_index} 不存在")
    result = set_power_limit(req.gpu_index, req.power_limit)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/task/pause")
def api_pause_task(req: TaskActionRequest):
    """暂停进程"""
    result = pause_task(req.pid)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/task/resume")
def api_resume_task(req: TaskActionRequest):
    """恢复进程"""
    result = resume_task(req.pid)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/task/terminate")
def api_terminate_task(req: TaskActionRequest):
    """终止进程"""
    result = terminate_task(req.pid)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/runtime/reservations")
def create_runtime_reservation(req: RuntimeReservationRequest):
    return runtime_store.create_reservation(req.model_dump())


@app.post("/api/runtime/jobs/launch")
def launch_runtime_job(req: RuntimeJobLaunchRequest):
    reservation = runtime_store.get_reservation(req.reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="reservation not found")
    return job_runtime.launch(req.model_dump())


@app.get("/api/runtime/jobs")
def list_runtime_jobs():
    return {"jobs": job_runtime.list_jobs()}


@app.get("/api/runtime/jobs/{job_handle}")
def get_runtime_job(job_handle: str):
    item = job_runtime.get_job(job_handle)
    if item is None:
        raise HTTPException(status_code=404, detail="runtime job not found")
    return item


@app.post("/api/runtime/jobs/{job_handle}/pause")
def pause_runtime_job(job_handle: str):
    return _apply_runtime_job_action(job_runtime.pause, job_handle)


@app.post("/api/runtime/jobs/{job_handle}/resume")
def resume_runtime_job(job_handle: str):
    return _apply_runtime_job_action(job_runtime.resume, job_handle)


@app.post("/api/runtime/jobs/{job_handle}/checkpoint")
def checkpoint_runtime_job(job_handle: str, req: RuntimeCheckpointRequest):
    return _apply_runtime_job_action(
        job_runtime.request_checkpoint,
        job_handle,
        req.model_dump(),
    )


@app.get("/api/runtime/jobs/{job_handle}/checkpoint")
def get_runtime_checkpoint(job_handle: str):
    item = job_runtime.get_checkpoint(job_handle)
    if item is None:
        raise HTTPException(status_code=404, detail="runtime job not found")
    return item


@app.post("/api/runtime/jobs/{job_handle}/restore")
def restore_runtime_job(job_handle: str, req: RuntimeJobRestoreRequest):
    if job_handle != req.job_handle:
        raise HTTPException(status_code=400, detail="runtime restore handle mismatch")
    reservation = runtime_store.get_reservation(req.reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="reservation not found")
    try:
        return job_runtime.restore(req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/runtime/jobs/{job_handle}/terminate")
def terminate_runtime_job(job_handle: str):
    item = job_runtime.terminate(job_handle)
    if item is None:
        raise HTTPException(status_code=404, detail="runtime job not found")
    return item


def _apply_runtime_job_action(action, job_handle: str, payload: dict | None = None):
    try:
        item = action(job_handle, payload) if payload is not None else action(job_handle)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="runtime job not found")
    return item


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
