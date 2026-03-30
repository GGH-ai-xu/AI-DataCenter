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


@router.get("/full-report")
async def export_full_governance_report(
    hours: float = Query(default=24, ge=1, le=168),
):
    """一键导出综合治理报告（能耗+调度+公平治理+碳排放）"""
    import json
    import time
    from datetime import datetime

    from app.main import app_state

    sections = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    sections.append(f"# GPU 共享治理综合报告\n\n> 生成时间：{now_str}  \n> 统计周期：过去 {hours} 小时\n")

    # 1. 能耗统计
    try:
        energy_metrics = await app_state.energy.get_metrics(hours)
        sections.append("## 一、能耗统计\n")
        sections.append(f"- 实时总功耗：**{energy_metrics.get('current_total_power', 0):.0f} W**")
        sections.append(f"- 日能耗：**{energy_metrics.get('kwh', 0):.2f} kWh**")
        sections.append(f"- 效率评分：**{energy_metrics.get('efficiency_score', 0):.0f}** / 100")
        sections.append(f"- 节能比例：**{energy_metrics.get('saving_pct', 0):.1f}%**\n")
    except Exception:
        sections.append("## 一、能耗统计\n\n数据暂不可用。\n")

    # 2. 碳排放
    try:
        carbon = await app_state.energy.get_carbon_data(hours)
        sections.append("## 二、碳排放\n")
        sections.append(f"- 今日碳排放：**{carbon.get('co2_kg', 0):.3f} kgCO₂**")
        sections.append(f"- 等效树木：**{carbon.get('trees_equivalent', 0):.1f}** 棵/天")
        sections.append(f"- 碳因子：{carbon.get('carbon_factor', 0.5703)}\n")
    except Exception:
        sections.append("## 二、碳排放\n\n数据暂不可用。\n")

    # 3. 公平治理
    try:
        fairness = await app_state.governance.get_fairness_report()
        fairness = app_state.privacy.sanitize_governance_report(fairness)
        overview = fairness.get("overview", {})
        sections.append("## 三、公平治理\n")
        sections.append(f"- 公平指数：**{overview.get('fairness_index', 100)}**（{overview.get('level', 'balanced')}）")
        sections.append(f"- 评估：{overview.get('summary', '当前共享较均衡。')}")
        users = fairness.get("users", [])
        if users:
            sections.append(f"- 活跃用户：{len(users)} 人")
            for u in users[:5]:
                sections.append(f"  - {u.get('username', '?')}：{u.get('task_count', 0)} 任务，占显存 {u.get('memory_share_pct', 0)}%")
        yield_candidates = fairness.get("yield_candidates", [])
        if yield_candidates:
            sections.append(f"- 建议让路任务：{len(yield_candidates)} 个")
        sections.append("")
    except Exception:
        sections.append("## 三、公平治理\n\n数据暂不可用。\n")

    # 4. 调度历史
    try:
        logs = await app_state.store.get_audit_logs(30)
        sections.append("## 四、治理操作记录（最近 30 条）\n")
        if logs:
            sections.append("| 时间 | 动作 | 目标 | 结果 | 来源 |")
            sections.append("| --- | --- | --- | --- | --- |")
            for log in logs[:30]:
                ts = datetime.fromtimestamp(log.get("timestamp", 0)).strftime("%m/%d %H:%M")
                sections.append(f"| {ts} | {log.get('action', '-')} | {log.get('target', '-')[:30]} | {log.get('status', '-')} | {log.get('operator', '-')} |")
        else:
            sections.append("暂无治理操作记录。")
        sections.append("")
    except Exception:
        sections.append("## 四、治理操作记录\n\n数据暂不可用。\n")

    # 5. AI 洞察
    if app_state.llm:
        try:
            gpus = await app_state.agent.get_all_gpus()
            if gpus:
                summary = await app_state.store.get_power_summary(hours)
                alerts = await app_state.store.get_alerts(limit=10)
                ai_report = await app_state.llm.generate_report(summary, alerts)
                sections.append("## 五、AI 分析报告\n")
                sections.append(ai_report or "AI 分析暂未生成。")
                sections.append("")
        except Exception:
            sections.append("## 五、AI 分析报告\n\n数据暂不可用。\n")

    sections.append("---\n\n*由 GPU 共享治理平台自动生成*")

    content = "\n".join(sections)
    content = app_state.privacy.mask_text(
        content,
        known_usernames=await app_state.store.get_known_usernames(),
    ) or content

    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=full-governance-report.md"},
    )
