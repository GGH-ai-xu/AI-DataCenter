"""能耗优化分析API - 11个端点提供能耗KPI、时段分析、效率评分、预测、碳排放、优化建议、历史对比、报告导出、调度回放"""

from fastapi import APIRouter, Query
from fastapi.responses import Response, JSONResponse

router = APIRouter(prefix="/api/energy", tags=["Energy"])


def _selected_gpu_indexes(app_state) -> list[int]:
    return app_state.import_context.selected_gpu_indexes()


@router.get("/metrics")
async def get_metrics(hours: float = Query(default=24.0, ge=0.5, le=168)):
    """核心KPI：总功耗、kWh、月费用、CO2"""
    from app.main import app_state
    return await app_state.energy.get_energy_metrics(
        hours,
        gpu_indexes=_selected_gpu_indexes(app_state),
    )


@router.get("/ai-insight")
async def get_ai_insight():
    """D2: AI趋势洞察"""
    from app.main import app_state
    result = await app_state.energy.get_ai_insight(
        gpu_indexes=_selected_gpu_indexes(app_state),
    )
    if result is None:
        return JSONResponse(status_code=404, content={"detail": "AI洞察不可用"})
    return result


@router.get("/ai-anomalies")
async def get_ai_anomalies():
    """D1: AI异常模式检测"""
    from app.main import app_state
    result = await app_state.energy.get_ai_anomaly_analysis(
        gpu_indexes=_selected_gpu_indexes(app_state),
    )
    if result is None:
        return JSONResponse(status_code=404, content={"detail": "AI异常检测不可用"})
    return result


@router.get("/time-breakdown")
async def get_time_breakdown(hours: float = Query(default=24.0, ge=1, le=168)):
    """峰/谷/平能耗占比分析"""
    from app.main import app_state
    return await app_state.energy.get_time_period_breakdown(
        hours,
        gpu_indexes=_selected_gpu_indexes(app_state),
    )


@router.get("/efficiency")
async def get_efficiency():
    """每卡效率评分"""
    from app.main import app_state
    return await app_state.energy.get_gpu_efficiency(
        gpu_indexes=_selected_gpu_indexes(app_state),
    )


@router.get("/prediction")
async def get_prediction(hours: int = Query(default=24, ge=1, le=72)):
    """功耗预测 + 置信带"""
    from app.main import app_state
    return await app_state.energy.get_power_prediction(
        hours,
        gpu_indexes=_selected_gpu_indexes(app_state),
    )


@router.get("/carbon")
async def get_carbon(hours: float = Query(default=24.0, ge=0.5, le=168)):
    """碳排放详情 + 等效树木"""
    from app.main import app_state
    return await app_state.energy.get_carbon_data(
        hours,
        gpu_indexes=_selected_gpu_indexes(app_state),
    )


@router.post("/optimize")
async def run_optimize():
    """一键AI优化分析"""
    from app.main import app_state
    return await app_state.energy.get_optimization_analysis(
        gpu_indexes=_selected_gpu_indexes(app_state),
    )


@router.get("/report")
async def get_report(hours: float = Query(default=24.0, ge=1, le=168)):
    """全KPI增强报告"""
    from app.main import app_state
    return await app_state.energy.get_full_report(
        hours,
        gpu_indexes=_selected_gpu_indexes(app_state),
    )


@router.get("/optimization-history")
async def get_optimization_history(hours: float = Query(default=72.0, ge=1, le=720)):
    """优化历史记录"""
    from app.main import app_state
    return await app_state.store.get_optimization_history(
        hours,
        gpu_indexes=_selected_gpu_indexes(app_state),
    )


@router.get("/schedule-history")
async def get_schedule_history(hours: float = Query(default=72.0, ge=1, le=720)):
    """调度历史回放"""
    from app.main import app_state
    return await app_state.energy.get_schedule_history(
        hours,
        gpu_indexes=_selected_gpu_indexes(app_state),
    )


@router.get("/history-comparison")
async def get_history_comparison(hours: float = Query(default=72.0, ge=1, le=720)):
    """优化效果历史对比"""
    from app.main import app_state
    return await app_state.energy.get_history_comparison(
        hours,
        gpu_indexes=_selected_gpu_indexes(app_state),
    )


@router.get("/export-report")
async def export_report(
    hours: float = Query(default=24.0, ge=1, le=168),
    format: str = Query(default="markdown", pattern="^(markdown|html)$"),
):
    """导出能耗分析报告"""
    from app.main import app_state
    content = await app_state.energy.generate_export_report(
        hours,
        format,
        gpu_indexes=_selected_gpu_indexes(app_state),
    )
    if format == "html":
        return Response(
            content=content,
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=energy-report.html"},
        )
    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=energy-report.md"},
    )
