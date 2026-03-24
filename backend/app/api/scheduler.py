"""调度策略API - 手动/自动调度控制"""

from fastapi import APIRouter

from app.models.schemas import PowerLimitRequest

router = APIRouter(prefix="/api/scheduler", tags=["Scheduler"])


@router.get("/status")
async def get_scheduler_status():
    """获取调度器状态"""
    from app.main import app_state
    from app.services.scheduler import get_time_period, get_time_period_label
    return {
        "auto_enabled": app_state.scheduler.auto_enabled,
        "time_period": get_time_period(),
        "time_period_label": get_time_period_label(),
    }


@router.post("/auto")
async def toggle_auto_schedule(enabled: bool = True):
    """启用/禁用自动调度"""
    from app.main import app_state
    app_state.scheduler.set_auto(enabled)
    return {"auto_enabled": enabled}


@router.post("/power-limit")
async def manual_power_limit(req: PowerLimitRequest):
    """手动设置GPU功耗上限"""
    from app.main import app_state
    result = await app_state.agent.set_power_limit(req.gpu_index, req.power_limit)
    return result


@router.post("/run-once")
async def run_schedule_once():
    """手动触发一次AI调度"""
    from app.main import app_state
    gpus = await app_state.agent.get_all_gpus()
    processes = await app_state.agent.get_processes()

    if not gpus:
        return {"error": "无法获取GPU数据"}

    # 先执行规则引擎
    rule_actions = await app_state.scheduler.run_rules(gpus, processes)
    rule_results = []
    if rule_actions:
        rule_results = await app_state.scheduler.execute_actions(rule_actions)

    # 再执行AI调度
    ai_strategy = await app_state.scheduler.run_ai_schedule(gpus, processes)
    ai_results = []
    if ai_strategy and "actions" in ai_strategy:
        ai_results = await app_state.scheduler.execute_actions(ai_strategy["actions"])

    return {
        "rule_actions": rule_actions,
        "rule_results": rule_results,
        "ai_strategy": ai_strategy,
        "ai_results": ai_results,
    }


@router.get("/report")
async def generate_report():
    """生成AI能耗分析报告"""
    from app.main import app_state
    if not app_state.llm:
        return {"report": "LLM服务未配置"}

    summary = await app_state.store.get_power_summary(24)
    alerts = await app_state.store.get_alerts(limit=20)
    report = await app_state.llm.generate_report(summary, alerts)
    return {"report": report}
