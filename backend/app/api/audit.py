"""治理操作审计日志API"""

import time
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/audit", tags=["Audit"])


@router.get("/logs")
async def get_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    hours: float = Query(default=72, ge=1, le=720),
):
    """获取治理操作审计日志"""
    from app.main import app_state

    logs = await app_state.store.get_audit_logs(limit=limit, hours=hours)
    return {"logs": logs, "total": len(logs)}
