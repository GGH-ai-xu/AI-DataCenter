"""公平治理API - 返回公平指数、用户画像与建议让路任务"""

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.models.schemas import UserGovernanceRuleUpdate

router = APIRouter(prefix="/api/governance", tags=["Governance"])


@router.get("/fairness")
async def get_fairness_governance():
    """获取用户公平治理分析结果"""
    from app.main import app_state

    report = await app_state.governance.get_fairness_report()
    return app_state.privacy.sanitize_governance_report(report)


@router.get("/rules")
async def get_governance_rules():
    """获取用户治理规则列表"""
    from app.main import app_state

    rules = await app_state.store.get_user_governance_rules()
    return {
        "rules": [
            app_state.privacy.sanitize_governance_rule(rule)
            for rule in rules.values()
        ]
    }


@router.post("/rules")
async def upsert_governance_rule(req: UserGovernanceRuleUpdate):
    """新增或更新单个用户治理规则"""
    from app.main import app_state
    username = app_state.privacy.resolve_username(
        req.username,
        await app_state.store.get_known_usernames(),
    )

    await app_state.store.upsert_user_governance_rule(
        username=username,
        role=req.role,
        max_tasks=req.max_tasks,
        max_gpu_count=req.max_gpu_count,
        max_memory_gb=req.max_memory_gb,
        allow_preempt=req.allow_preempt,
        note=req.note,
    )
    rules = await app_state.store.get_user_governance_rules()
    return {
        "success": True,
        "rule": app_state.privacy.sanitize_governance_rule(rules.get(username)),
    }


@router.delete("/rules/{username}")
async def delete_governance_rule(username: str):
    """删除单个用户治理规则"""
    from app.main import app_state
    raw_username = app_state.privacy.resolve_username(
        username,
        await app_state.store.get_known_usernames(),
    )

    await app_state.store.delete_user_governance_rule(raw_username)
    return {
        "success": True,
        "username": app_state.privacy.mask_username(raw_username),
    }


@router.get("/export-report")
async def export_governance_report(
    format: str = Query(default="markdown", pattern="^(markdown|html)$"),
):
    """导出治理报告"""
    from app.main import app_state

    content = await app_state.governance.generate_export_report(format)
    content = app_state.privacy.mask_text(
        content,
        known_usernames=await app_state.store.get_known_usernames(),
    ) or ""
    if format == "html":
        return Response(
            content=content,
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=governance-report.html"},
        )
    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=governance-report.md"},
    )
