"""告警管理API"""

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


@router.get("/")
async def get_alerts(
    limit: int = Query(default=50, ge=1, le=500),
    unack_only: bool = Query(default=False),
):
    """获取告警列表"""
    from app.main import app_state
    alerts = await app_state.store.get_alerts(limit, unack_only)
    return {"alerts": alerts}


@router.post("/acknowledge/{alert_id}")
async def acknowledge_alert(alert_id: int):
    """确认告警"""
    from app.main import app_state
    await app_state.store.acknowledge_alert(alert_id)
    return {"success": True, "alert_id": alert_id}
