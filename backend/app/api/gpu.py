"""GPU数据查询API - 实时数据 + 历史趋势"""

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/gpu", tags=["GPU"])


@router.get("/realtime")
async def get_realtime():
    """获取所有GPU实时状态"""
    from app.main import app_state
    gpus = await app_state.agent.get_all_gpus()
    system = await app_state.agent.get_system_info()
    return {"gpus": gpus, "system": system}


@router.get("/history/{gpu_index}")
async def get_history(
    gpu_index: int,
    hours: float = Query(default=1.0, ge=0.1, le=168),
):
    """查询指定GPU的历史数据"""
    from app.main import app_state
    data = await app_state.store.get_gpu_history(gpu_index, hours)
    return {"gpu_index": gpu_index, "hours": hours, "data": data}


@router.get("/summary")
async def get_power_summary(hours: float = Query(default=24.0, ge=1, le=168)):
    """获取功耗统计摘要"""
    from app.main import app_state
    summary = await app_state.store.get_power_summary(hours)
    return summary
