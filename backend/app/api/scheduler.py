"""调度策略API - 手动/自动调度控制"""

from collections import Counter
from datetime import datetime

from fastapi import APIRouter, Body, HTTPException

from app.models.schemas import PowerBudgetConfigRequest, PowerLimitRequest, ScheduleRunRequest
from app.services.runtime_snapshot import (
    has_runtime_snapshot,
    snapshot_scoped_gpus,
    snapshot_scoped_processes,
)

router = APIRouter(prefix="/api/scheduler", tags=["Scheduler"])


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_watts(value) -> str:
    return f"{_safe_float(value):.1f}W"


def _format_timestamp(value) -> str:
    ts = _safe_float(value)
    if ts <= 0:
        return "未知时间"
    return datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")


def build_fallback_report(summary: dict, alerts: list[dict]) -> str:
    """在未配置 LLM 或 LLM 不可用时，生成可读的基础版 Markdown 报告。"""
    hours = _safe_float(summary.get("hours"), 24.0)
    gpus = summary.get("gpus") or []
    total_avg_power = _safe_float(summary.get("total_avg_power"))
    severity_counter = Counter(str(item.get("severity") or "unknown") for item in alerts)
    type_counter = Counter(str(item.get("alert_type") or "unknown") for item in alerts)

    lines = [
        "# 调度能耗分析报告（基础版）",
        "",
        "> 当前未配置 LLM，以下报告由平台基于历史功耗与告警记录自动生成，可用于基础验收与日常巡检。",
        "",
        "## 1. 数据概览",
        f"- 统计窗口：最近 {hours:.0f} 小时",
        f"- 纳入统计的 GPU 数量：{len(gpus)} 张",
        f"- 集群平均总功率：{_format_watts(total_avg_power)}",
        f"- 近期告警总数：{len(alerts)} 条",
    ]

    if not gpus:
        lines.extend([
            "",
            "## 2. GPU 分布",
            "- 当前统计窗口内暂无 GPU 历史样本，无法形成负载分布判断。",
            "",
            "## 3. 风险与告警",
            f"- 最近告警数：{len(alerts)} 条",
            "",
            "## 4. 建议动作",
            "- 先保持 Agent 在线运行 15 到 30 分钟，积累真实功耗样本后再生成报告。",
            "- 检查采集代理与后端连接状态，确认历史数据库正在持续写入。",
            "- 如果当前正在做真实治理验证，建议手动执行一次调度，并观察预算页是否出现动作记录。",
            "",
            "## 5. 预估节能潜力",
            "- 当前数据不足，暂不输出节能估算。",
        ])
        return "\n".join(lines)

    avg_sorted = sorted(gpus, key=lambda item: _safe_float(item.get("avg_power")), reverse=True)
    peak_gpu = max(gpus, key=lambda item: _safe_float(item.get("max_power")))
    busiest_gpu = avg_sorted[0]
    calmest_gpu = avg_sorted[-1]
    imbalance_gap = max(0.0, _safe_float(busiest_gpu.get("avg_power")) - _safe_float(calmest_gpu.get("avg_power")))

    lines.extend([
        "",
        "## 2. GPU 分布",
    ])
    for gpu in avg_sorted:
        lines.append(
            "- GPU {idx}: 平均 {avg} / 峰值 {peak} / 最低 {min_power} / 样本 {samples} 条".format(
                idx=gpu.get("gpu_index", "?"),
                avg=_format_watts(gpu.get("avg_power")),
                peak=_format_watts(gpu.get("max_power")),
                min_power=_format_watts(gpu.get("min_power")),
                samples=int(_safe_float(gpu.get("samples"))),
            )
        )

    lines.extend([
        "",
        "## 3. 风险与告警",
        f"- critical：{severity_counter.get('critical', 0)} 条",
        f"- warning：{severity_counter.get('warning', 0)} 条",
        f"- info：{severity_counter.get('info', 0)} 条",
        f"- 温度类告警：{type_counter.get('temperature', 0)} 条",
        f"- 功耗类告警：{type_counter.get('power', 0)} 条",
        f"- 显存类告警：{type_counter.get('memory', 0)} 条",
    ])

    if alerts:
        for index, item in enumerate(alerts[:5], start=1):
            lines.append(
                "- 告警摘录 {index}：[{time}] GPU {gpu} / {severity} / {message}".format(
                    index=index,
                    time=_format_timestamp(item.get("timestamp")),
                    gpu=item.get("gpu_index", "?"),
                    severity=item.get("severity", "unknown"),
                    message=item.get("message", "无详情"),
                )
            )
    else:
        lines.append("- 最近未发现新的告警记录。")

    recommendations: list[str] = []
    estimated_saving_watts = 0.0

    if severity_counter.get("critical", 0) > 0:
        recommendations.append("优先处置 critical 告警对应 GPU，先检查散热、风扇与持续高功耗任务，再决定是否执行强制限功率。")
        estimated_saving_watts += min(80.0, _safe_float(peak_gpu.get("max_power")) * 0.12)

    if type_counter.get("temperature", 0) > 0:
        recommendations.append("近期存在温度异常，建议对高温 GPU 先下调 20W 到 40W 功耗上限，并检查机箱风道与环境温度。")
        estimated_saving_watts += 20.0

    if type_counter.get("power", 0) > 0 or _safe_float(peak_gpu.get("max_power")) >= 300:
        recommendations.append(
            f"GPU {peak_gpu.get('gpu_index', '?')} 峰值功耗最高，建议在高峰时段优先纳入预算治理，避免单卡长时间贴近上限运行。"
        )
        estimated_saving_watts += 25.0

    if imbalance_gap >= 60:
        recommendations.append(
            f"当前 GPU 负载分布不均，最忙与最闲卡平均功耗差 {imbalance_gap:.1f}W，建议调整任务分布或结合优先级做迁移/暂停。"
        )
        estimated_saving_watts += min(50.0, imbalance_gap * 0.25)

    if not recommendations:
        recommendations.append("当前集群整体较平稳，可继续保持预算治理开启，并通过一次真实调度观察是否还能进一步压缩低价值负载。")
        if total_avg_power > 0:
            estimated_saving_watts += min(25.0, total_avg_power * 0.05)

    lines.extend([
        "",
        "## 4. 建议动作",
    ])
    for item in recommendations:
        lines.append(f"- {item}")

    estimated_saving_watts = round(min(estimated_saving_watts, max(total_avg_power * 0.25, 0.0)), 1)
    estimated_saving_pct = round((estimated_saving_watts / total_avg_power * 100.0), 1) if total_avg_power > 0 else 0.0

    lines.extend([
        "",
        "## 5. 预估节能潜力",
        f"- 规则估算可优化空间：{_format_watts(estimated_saving_watts)}",
        f"- 对应平均节能比例：{estimated_saving_pct:.1f}%",
        f"- 当前最高平均功耗 GPU：GPU {busiest_gpu.get('gpu_index', '?')}（{_format_watts(busiest_gpu.get('avg_power'))}）",
        f"- 当前最低平均功耗 GPU：GPU {calmest_gpu.get('gpu_index', '?')}（{_format_watts(calmest_gpu.get('avg_power'))}）",
    ])

    return "\n".join(lines)


async def _scoped_gpus(app_state) -> list[dict]:
    snapshot = getattr(app_state, "latest_runtime_snapshot", {})
    if has_runtime_snapshot(snapshot):
        return snapshot_scoped_gpus(snapshot)
    gpus = await app_state.agent.get_all_gpus()
    return app_state.import_context.filter_gpus(gpus)


async def _scoped_processes(app_state) -> list[dict]:
    snapshot = getattr(app_state, "latest_runtime_snapshot", {})
    if has_runtime_snapshot(snapshot):
        return snapshot_scoped_processes(snapshot)
    processes = await app_state.agent.get_processes()
    return app_state.import_context.filter_processes(processes)


def _selected_gpu_indexes(app_state) -> list[int]:
    import_context = getattr(app_state, "import_context", None)
    if not import_context:
        return []
    return import_context.selected_gpu_indexes()


def _ensure_gpu_in_scope(app_state, gpu_index: int):
    try:
        app_state.import_context.ensure_gpu_allowed(gpu_index)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/status")
async def get_scheduler_status():
    """获取调度器状态"""
    from app.main import app_state
    from app.services.scheduler import get_time_period, get_time_period_label

    gpus = await _scoped_gpus(app_state)
    return {
        "auto_enabled": app_state.scheduler.auto_enabled,
        "time_period": get_time_period(),
        "time_period_label": get_time_period_label(),
        "budget": app_state.scheduler.get_budget_status(gpus),
        "carbon": app_state.scheduler.get_carbon_budget_status(gpus or []),
    }


@router.post("/auto")
async def toggle_auto_schedule(enabled: bool = True):
    """启用/禁用自动调度"""
    from app.main import app_state
    app_state.scheduler.set_auto(enabled)
    return {"auto_enabled": enabled}


@router.post("/budget")
async def configure_power_budget(req: PowerBudgetConfigRequest):
    """配置总功率预算治理参数"""
    from app.main import app_state

    app_state.scheduler.configure_budget(req.enabled, req.total_power_budget)
    gpus = await _scoped_gpus(app_state)
    return {
        "success": True,
        "budget": app_state.scheduler.get_budget_status(gpus),
    }


@router.get("/carbon-budget")
async def get_carbon_budget():
    """获取碳预算状态"""
    from app.main import app_state

    gpus = await _scoped_gpus(app_state)
    return app_state.scheduler.get_carbon_budget_status(gpus or [])


@router.post("/carbon-budget")
async def set_carbon_budget(req: dict):
    """配置碳预算"""
    from app.main import app_state

    enabled = bool(req.get("enabled", False))
    daily_kg = float(req.get("daily_budget_kg", 50.0))
    app_state.scheduler.configure_carbon_budget(enabled, daily_kg)
    gpus = await _scoped_gpus(app_state)
    return {
        "success": True,
        "carbon_budget": app_state.scheduler.get_carbon_budget_status(gpus or []),
    }


@router.post("/power-limit")
async def manual_power_limit(req: PowerLimitRequest):
    """手动设置GPU功耗上限"""
    from app.main import app_state

    if not req.acknowledge_risk:
        raise HTTPException(status_code=400, detail="真实限功率操作需要先确认风险")
    _ensure_gpu_in_scope(app_state, req.gpu_index)
    app_state.scheduler.clear_managed_gpu(req.gpu_index)
    result = await app_state.agent.set_power_limit(req.gpu_index, req.power_limit)
    result["applied"] = bool(result.get("success"))
    return result


@router.post("/run-once")
async def run_schedule_once(req: ScheduleRunRequest | None = Body(default=None)):
    """手动触发一次AI调度"""
    from app.main import app_state
    req = req or ScheduleRunRequest()
    if not req.acknowledge_risk:
        raise HTTPException(status_code=400, detail="真实调度执行需要先确认风险")

    gpus = await _scoped_gpus(app_state)
    processes = await _scoped_processes(app_state)

    if not gpus:
        return {"error": "当前导入范围内无法获取GPU数据"}

    # 先执行规则引擎
    rule_actions = await app_state.scheduler.run_rules(gpus, processes)
    rule_results = []
    if rule_actions:
        rule_results = await app_state.scheduler.execute_actions(rule_actions)

    # 再执行总功率预算调度
    budget_actions = await app_state.scheduler.run_budget_schedule(gpus, processes)
    budget_results = []
    if budget_actions:
        budget_results = await app_state.scheduler.execute_actions(budget_actions)

    # 再执行AI调度
    ai_strategy = await app_state.scheduler.run_ai_schedule(gpus, processes)
    ai_results = []
    if ai_strategy and "actions" in ai_strategy:
        ai_results = await app_state.scheduler.execute_actions(ai_strategy["actions"])

    latest_gpus = await _scoped_gpus(app_state)

    return {
        "rule_actions": rule_actions,
        "rule_results": rule_results,
        "budget_actions": budget_actions,
        "budget_results": budget_results,
        "ai_strategy": ai_strategy,
        "ai_results": ai_results,
        "budget": app_state.scheduler.get_budget_status(latest_gpus or gpus),
        "carbon": app_state.scheduler.get_carbon_budget_status(latest_gpus or gpus),
    }


@router.get("/audit-log")
async def get_audit_log(limit: int = 100):
    """获取治理操作审计日志"""
    from app.main import app_state
    logs = await app_state.store.get_audit_logs(limit)
    return {"logs": logs, "total": len(logs)}


@router.get("/evaluation")
async def get_schedule_evaluation():
    """获取最近一次 AI 调度效果评估（D4 闭环反馈）"""
    from app.main import app_state

    # 优先返回缓存的评估结果
    cached = app_state.scheduler._last_evaluation
    if cached:
        return {"evaluation": cached, "source": "cached"}

    # 尝试实时评估
    gpus = await _scoped_gpus(app_state)
    if not gpus:
        return {"evaluation": None, "message": "当前导入范围内暂无 GPU 数据，无法评估"}

    result = await app_state.scheduler.evaluate_last_schedule(gpus)
    if result:
        return {"evaluation": result, "source": "realtime"}

    # 无上次调度记录时生成基础评估
    return {
        "evaluation": {
            "score": 0,
            "verdict": "暂无评估",
            "effective_actions": [],
            "ineffective_actions": [],
            "suggestions": ["请先执行一次调度，系统将自动评估调度效果"],
        },
        "source": "none",
    }


@router.get("/report")
async def generate_report():
    """生成AI能耗分析报告"""
    from app.main import app_state

    gpu_indexes = _selected_gpu_indexes(app_state)
    if gpu_indexes:
        summary = await app_state.store.get_power_summary(24, gpu_indexes=gpu_indexes)
        alerts = await app_state.store.get_alerts(limit=20, gpu_indexes=gpu_indexes)
    else:
        summary = await app_state.store.get_power_summary(24)
        alerts = await app_state.store.get_alerts(limit=20)

    if app_state.llm:
        report = await app_state.llm.generate_report(summary, alerts)
        if report and not str(report).startswith("报告生成失败"):
            return {"report": report, "source": "llm"}

    return {
        "report": build_fallback_report(summary, alerts),
        "source": "fallback",
    }
