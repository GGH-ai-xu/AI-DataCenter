"""告警管理API"""

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


@router.get("/")
async def get_alerts(
    limit: int = Query(default=50, ge=1, le=500),
    unack_only: bool = Query(default=False),
):
    """获取告警列表"""
    from app.main import app_state

    alerts = await app_state.store.get_alerts(
        limit,
        unack_only,
        gpu_indexes=app_state.import_context.selected_gpu_indexes(),
    )
    return {"alerts": alerts}


@router.post("/acknowledge/{alert_id}")
async def acknowledge_alert(alert_id: int):
    """确认告警"""
    from app.main import app_state

    alert = await app_state.store.get_alert_by_id(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    try:
        app_state.import_context.ensure_gpu_allowed(alert["gpu_index"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await app_state.store.acknowledge_alert(alert_id)
    return {"success": True, "alert_id": alert_id}
