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
from collectors.system_monitor import get_system_info
from collectors.task_monitor import get_all_gpu_processes
from controllers.power_control import set_power_limit
from controllers.task_control import pause_task, resume_task, terminate_task
from config import HOST, PORT, POWER_LIMIT_MIN, POWER_LIMIT_MAX

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    gpu_monitor.init()
    logger.info(f"Agent启动，检测到 {gpu_monitor.device_count} 张GPU")
    yield
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
    """获取系统资源信息"""
    return get_system_info()


@app.get("/api/processes")
def get_processes():
    """获取所有GPU上的进程列表"""
    procs = get_all_gpu_processes(gpu_monitor.device_count)
    return {"processes": procs}


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
