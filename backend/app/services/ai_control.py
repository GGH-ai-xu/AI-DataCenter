"""AI 执行控制台服务 - 自然语言动作规划与安全执行"""

from __future__ import annotations

import json
import re
from typing import Any

from app.services.scheduler import get_time_period_label


SUPPORTED_ACTIONS = {
    "set_power_limit",
    "pause_task",
    "resume_task",
    "terminate_task",
    "set_task_priority",
    "configure_budget",
    "run_schedule_once",
}

HIGH_RISK_ACTIONS = {"terminate_task"}
MEDIUM_RISK_ACTIONS = {
    "set_power_limit",
    "pause_task",
    "resume_task",
    "configure_budget",
    "run_schedule_once",
}


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _priority_from_text(text: str) -> str | None:
    normalized = (text or "").lower()
    if "紧急" in normalized or "urgent" in normalized:
        return "urgent"
    if "可延迟" in normalized or "延迟" in normalized or "deferrable" in normalized:
        return "deferrable"
    if "普通" in normalized or "normal" in normalized:
        return "normal"
    return None


def _priority_label(priority: str | None) -> str:
    return {
        "urgent": "紧急",
        "normal": "普通",
        "deferrable": "可延迟",
    }.get(priority or "", priority or "未知")


def _action_label(action: str) -> str:
    return {
        "set_power_limit": "设置单卡功耗上限",
        "pause_task": "暂停任务",
        "resume_task": "恢复任务",
        "terminate_task": "终止任务",
        "set_task_priority": "调整任务优先级",
        "configure_budget": "调整总功率预算",
        "run_schedule_once": "执行一次综合调度",
    }.get(action, action)


def _risk_level_for_action(action: str) -> str:
    if action in HIGH_RISK_ACTIONS:
        return "high"
    if action in MEDIUM_RISK_ACTIONS:
        return "medium"
    return "low"


def _merge_risk_levels(levels: list[str]) -> str:
    if "high" in levels:
        return "high"
    if "medium" in levels:
        return "medium"
    return "low"


def _build_process_label(proc: dict) -> str:
    return (
        f"PID {proc.get('pid', '-')}"
        f" · {proc.get('name') or 'unknown'}"
        f" · GPU {proc.get('gpu_index', '-')}"
        f" · {_priority_label(proc.get('priority'))}"
    )


def _find_pid(text: str) -> int | None:
    match = re.search(r"(?:pid|进程)\s*[:：]?\s*(\d+)", text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))

    standalone = re.search(r"\b(\d{3,7})\b", text)
    if standalone:
        return int(standalone.group(1))
    return None


def _find_gpu_index(text: str) -> int | None:
    match = re.search(r"gpu\s*[:：]?\s*(\d+)", text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"显卡\s*[:：]?\s*(\d+)", text)
    if match:
        return int(match.group(1))
    return None


def _find_power_limit(text: str) -> int | None:
    match = re.search(r"(\d{3})\s*w\b", text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d{3})\s*瓦", text)
    if match:
        return int(match.group(1))
    return None


def _find_budget_value(text: str) -> int | None:
    match = re.search(r"(?:预算|总功率|功率预算).*?(\d{3,4})\s*(?:w|瓦)?", text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


async def build_control_context(app_state) -> dict:
    gpus = await app_state.agent.get_all_gpus() or []
    gpus = app_state.import_context.filter_gpus(gpus)
    processes = await app_state.agent.get_processes() or []
    processes = app_state.import_context.filter_processes(processes)
    priorities = await app_state.store.get_all_task_priorities()

    enriched_processes: list[dict] = []
    for proc in processes:
        cloned = dict(proc)
        cloned["priority"] = priorities.get(
            cloned.get("pid"),
            cloned.get("priority", "normal"),
        )
        enriched_processes.append(cloned)

    manageable_processes = [
        proc for proc in enriched_processes
        if proc.get("manageable", True)
    ]
    manageable_processes.sort(
        key=lambda item: (
            -(item.get("gpu_memory_used", 0) or 0),
            item.get("pid", 0),
        )
    )
    top_manageable = manageable_processes[:12]
    llm_processes = (
        app_state.privacy.sanitize_processes(top_manageable)
        if app_state.privacy
        else [dict(proc) for proc in top_manageable]
    )
    llm_gpus = [
        {
            key: gpu.get(key)
            for key in (
                "index",
                "name",
                "temperature",
                "power_usage",
                "power_limit",
                "gpu_utilization",
                "memory_used",
                "memory_total",
            )
        }
        for gpu in gpus
    ]
    budget = app_state.scheduler.get_budget_status(gpus)

    llm_context = {
        "time_period": get_time_period_label(),
        "budget": budget,
        "gpus": llm_gpus,
        "manageable_processes": [
            {
                "pid": proc.get("pid"),
                "gpu_index": proc.get("gpu_index"),
                "name": proc.get("name"),
                "username": proc.get("username"),
                "priority": proc.get("priority", "normal"),
                "gpu_memory_used": proc.get("gpu_memory_used", 0),
                "manageable_reason": proc.get("manageable_reason", ""),
                "command": proc.get("command", ""),
            }
            for proc in llm_processes
        ],
    }

    return {
        "gpus": gpus,
        "processes": enriched_processes,
        "process_map": {
            _to_int(proc.get("pid"), -1): proc
            for proc in enriched_processes
            if _to_int(proc.get("pid"), -1) > 0
        },
        "gpu_map": {
            _to_int(gpu.get("index"), -1): gpu
            for gpu in gpus
            if _to_int(gpu.get("index"), -1) >= 0
        },
        "budget": budget,
        "llm_context": json.dumps(llm_context, ensure_ascii=False, indent=2),
    }


def _enrich_action(action: dict, context: dict) -> dict:
    item = {
        "action": action.get("action"),
        "target": dict(action.get("target") or {}),
        "reason": (action.get("reason") or "").strip(),
    }
    act = item["action"]
    target = item["target"]
    process_map = context["process_map"]
    gpu_map = context["gpu_map"]
    blocked_reason = ""
    target_label = "-"
    valid = act in SUPPORTED_ACTIONS

    if not valid:
        blocked_reason = "动作类型不受支持"
    elif act == "set_power_limit":
        gpu_index = _to_int(target.get("gpu_index"), -1)
        power_limit = _to_int(target.get("power_limit"), 0)
        target["gpu_index"] = gpu_index
        target["power_limit"] = power_limit
        if gpu_index not in gpu_map:
            valid = False
            blocked_reason = f"GPU {gpu_index} 不存在"
        elif not (100 <= power_limit <= 350):
            valid = False
            blocked_reason = "功耗限制必须在 100W-350W 之间"
        else:
            gpu = gpu_map[gpu_index]
            target_label = (
                f"GPU {gpu_index} · {gpu.get('name') or 'unknown'} · "
                f"{gpu.get('power_usage', 0)}W -> {power_limit}W"
            )
    elif act in {"pause_task", "resume_task", "terminate_task", "set_task_priority"}:
        pid = _to_int(target.get("pid"), -1)
        target["pid"] = pid
        proc = process_map.get(pid)
        if not proc:
            valid = False
            blocked_reason = f"PID {pid} 不在当前 GPU 任务列表中"
        else:
            target_label = _build_process_label(proc)
            if act in {"pause_task", "resume_task", "terminate_task"} and not proc.get("manageable", True):
                valid = False
                blocked_reason = proc.get("manageable_reason") or "该进程不允许执行治理动作"
            if act == "set_task_priority":
                priority = _priority_from_text(str(target.get("priority", ""))) or str(target.get("priority", "")).strip()
                target["priority"] = priority
                if priority not in {"urgent", "normal", "deferrable"}:
                    valid = False
                    blocked_reason = "优先级必须为 urgent、normal 或 deferrable"
                else:
                    target_label = f"{target_label} -> {_priority_label(priority)}"
    elif act == "configure_budget":
        enabled = bool(target.get("enabled", True))
        total_power_budget = _to_int(target.get("total_power_budget"), 0)
        target["enabled"] = enabled
        target["total_power_budget"] = total_power_budget
        if not (400 <= total_power_budget <= 5000):
            valid = False
            blocked_reason = "总功率预算必须在 400W-5000W 之间"
        else:
            target_label = f"{'启用' if enabled else '禁用'}总功率预算 · {total_power_budget}W"
    elif act == "run_schedule_once":
        target_label = "执行一次规则 + 预算 + AI 综合调度"

    item["valid"] = valid
    item["blocked_reason"] = blocked_reason
    item["target_label"] = target_label
    item["risk_level"] = _risk_level_for_action(act or "")
    return item


def _build_heuristic_plan(message: str) -> dict:
    text = (message or "").strip()
    lowered = text.lower()
    actions: list[dict] = []
    warnings: list[str] = []

    if any(word in lowered for word in ("调度一次", "执行调度", "运行调度", "schedule once")):
        actions.append({
            "action": "run_schedule_once",
            "target": {},
            "reason": "根据用户指令手动执行一次综合调度",
        })

    budget_value = _find_budget_value(lowered)
    if budget_value is not None:
        actions.append({
            "action": "configure_budget",
            "target": {"enabled": True, "total_power_budget": budget_value},
            "reason": f"根据用户指令将总功率预算设置为 {budget_value}W",
        })

    gpu_index = _find_gpu_index(lowered)
    power_limit = _find_power_limit(lowered)
    if gpu_index is not None and power_limit is not None and any(
        word in lowered for word in (
            "限功率",
            "功率限制",
            "功耗限制",
            "功耗上限",
            "功率上限",
            "上限",
            "调到",
            "设到",
            "设成",
            "设为",
            "power limit",
            "cap",
        )
    ):
        actions.append({
            "action": "set_power_limit",
            "target": {"gpu_index": gpu_index, "power_limit": power_limit},
            "reason": f"根据用户指令将 GPU {gpu_index} 的功耗上限设置为 {power_limit}W",
        })

    pid = _find_pid(lowered)
    if pid is not None:
        if any(word in lowered for word in ("暂停", "挂起", "pause")):
            actions.append({
                "action": "pause_task",
                "target": {"pid": pid},
                "reason": f"根据用户指令暂停 PID {pid}",
            })
        elif any(word in lowered for word in ("恢复", "继续", "resume")):
            actions.append({
                "action": "resume_task",
                "target": {"pid": pid},
                "reason": f"根据用户指令恢复 PID {pid}",
            })
        elif any(word in lowered for word in ("终止", "结束", "杀掉", "terminate", "kill")):
            actions.append({
                "action": "terminate_task",
                "target": {"pid": pid},
                "reason": f"根据用户指令终止 PID {pid}",
            })

        priority = _priority_from_text(lowered)
        if priority:
            actions.append({
                "action": "set_task_priority",
                "target": {"pid": pid, "priority": priority},
                "reason": f"根据用户指令把 PID {pid} 调整为 {_priority_label(priority)}",
            })

    if not actions:
        warnings.append("暂时无法从这句话中提取可执行动作，请明确给出 PID、GPU 编号或预算值。")

    risk_level = _merge_risk_levels([
        _risk_level_for_action(item["action"])
        for item in actions
    ])
    return {
        "planner": "rule",
        "summary": "已按规则解析用户指令并生成执行计划。" if actions else "暂时无法解析成可执行动作。",
        "risk_level": risk_level,
        "requires_confirmation": any(item["action"] in HIGH_RISK_ACTIONS for item in actions),
        "warnings": warnings,
        "actions": actions,
    }


async def plan_control_actions(app_state, message: str) -> dict:
    context = await build_control_context(app_state)

    llm_plan = None
    planner = "rule"
    if app_state.llm:
        llm_plan = await app_state.llm.generate_control_plan(message, context["llm_context"])
        if llm_plan and isinstance(llm_plan, dict):
            planner = "llm"

    raw_plan = llm_plan if planner == "llm" else _build_heuristic_plan(message)
    actions = raw_plan.get("actions") or []
    enriched_actions = [_enrich_action(item, context) for item in actions]
    warnings = list(raw_plan.get("warnings") or [])
    if planner == "llm" and not enriched_actions:
        fallback_plan = _build_heuristic_plan(message)
        raw_plan = fallback_plan
        enriched_actions = [_enrich_action(item, context) for item in (fallback_plan.get("actions") or [])]
        warnings.extend(fallback_plan.get("warnings") or [])
        planner = "rule"

    invalid_count = sum(1 for item in enriched_actions if not item.get("valid"))
    if invalid_count:
        warnings.append(f"当前计划中有 {invalid_count} 条动作不可直接执行，请先检查目标是否真实存在。")

    risk_level = raw_plan.get("risk_level") or _merge_risk_levels(
        [item.get("risk_level", "low") for item in enriched_actions]
    )
    requires_confirmation = bool(raw_plan.get("requires_confirmation")) or any(
        item.get("risk_level") == "high" for item in enriched_actions
    )

    return {
        "planner": planner,
        "summary": raw_plan.get("summary") or "已生成执行计划。",
        "risk_level": risk_level,
        "requires_confirmation": requires_confirmation,
        "warnings": warnings[:6],
        "actions": enriched_actions,
        "context": {
            "gpu_count": len(context["gpus"]),
            "manageable_process_count": len([
                proc for proc in context["processes"]
                if proc.get("manageable", True)
            ]),
            "budget": context["budget"],
            "time_period": get_time_period_label(),
        },
    }


async def _run_schedule_once(app_state) -> dict:
    gpus = await app_state.agent.get_all_gpus()
    gpus = app_state.import_context.filter_gpus(gpus)
    processes = await app_state.agent.get_processes()
    processes = app_state.import_context.filter_processes(processes)
    if not gpus:
        return {"success": False, "error": "当前导入范围内无法获取 GPU 数据"}

    rule_actions = await app_state.scheduler.run_rules(gpus, processes)
    rule_results = await app_state.scheduler.execute_actions(rule_actions) if rule_actions else []

    budget_actions = await app_state.scheduler.run_budget_schedule(gpus, processes)
    budget_results = await app_state.scheduler.execute_actions(budget_actions) if budget_actions else []

    ai_strategy = await app_state.scheduler.run_ai_schedule(gpus, processes)
    ai_actions = ai_strategy.get("actions", []) if ai_strategy else []
    ai_results = await app_state.scheduler.execute_actions(ai_actions) if ai_actions else []

    return {
        "success": True,
        "rule_results": rule_results,
        "budget_results": budget_results,
        "ai_results": ai_results,
    }


async def execute_control_actions(
    app_state,
    actions: list[dict],
) -> dict:
    context = await build_control_context(app_state)
    results = []
    action_levels = []

    for action in actions:
        enriched = _enrich_action(action, context)
        result = {
            "action": enriched.get("action"),
            "label": _action_label(enriched.get("action") or ""),
            "target": enriched.get("target", {}),
            "target_label": enriched.get("target_label", "-"),
            "reason": enriched.get("reason", ""),
            "risk_level": enriched.get("risk_level", "low"),
            "success": False,
            "applied": False,
        }
        action_levels.append(result["risk_level"])

        if not enriched.get("valid"):
            result["error"] = enriched.get("blocked_reason") or "动作不可执行"
            results.append(result)
            continue

        try:
            act = enriched["action"]
            target = enriched["target"]

            if act == "set_power_limit":
                app_state.import_context.ensure_gpu_allowed(target["gpu_index"])
                app_state.scheduler.clear_managed_gpu(target["gpu_index"])
                response = await app_state.agent.set_power_limit(
                    target["gpu_index"],
                    target["power_limit"],
                )
                result["success"] = bool(response.get("success"))
                result["applied"] = result["success"]
                if not result["success"]:
                    result["error"] = response.get("error", "设置功耗上限失败")
            elif act == "pause_task":
                app_state.import_context.ensure_process_allowed(
                    target["pid"],
                    context["processes"],
                )
                response = await app_state.agent.pause_task(target["pid"])
                result["success"] = bool(response.get("success"))
                result["applied"] = result["success"]
                if not result["success"]:
                    result["error"] = response.get("error", "暂停任务失败")
            elif act == "resume_task":
                app_state.import_context.ensure_process_allowed(
                    target["pid"],
                    context["processes"],
                )
                response = await app_state.agent.resume_task(target["pid"])
                result["success"] = bool(response.get("success"))
                result["applied"] = result["success"]
                if not result["success"]:
                    result["error"] = response.get("error", "恢复任务失败")
            elif act == "terminate_task":
                app_state.import_context.ensure_process_allowed(
                    target["pid"],
                    context["processes"],
                )
                response = await app_state.agent.terminate_task(target["pid"])
                result["success"] = bool(response.get("success"))
                result["applied"] = result["success"]
                result["forced"] = bool(response.get("forced"))
                if not result["success"]:
                    result["error"] = response.get("error", "终止任务失败")
            elif act == "set_task_priority":
                app_state.import_context.ensure_process_allowed(
                    target["pid"],
                    context["processes"],
                )
                await app_state.store.set_task_priority(
                    target["pid"],
                    target["priority"],
                )
                result["success"] = True
                result["applied"] = True
            elif act == "configure_budget":
                app_state.scheduler.configure_budget(
                    target["enabled"],
                    target["total_power_budget"],
                )
                result["success"] = True
                result["applied"] = True
            elif act == "run_schedule_once":
                schedule_result = await _run_schedule_once(app_state)
                result["success"] = bool(schedule_result.get("success"))
                result["applied"] = result["success"]
                result["details"] = schedule_result
                if not result["success"]:
                    result["error"] = schedule_result.get("error", "执行调度失败")
            else:
                result["error"] = "动作类型不受支持"
        except Exception as exc:
            result["error"] = str(exc)

        results.append(result)

        # 记录治理审计日志
        try:
            await app_state.store.save_audit_log(
                action=result.get("action", ""),
                target=str(result.get("target", {})),
                reason=result.get("reason", ""),
                operator="ai_console",
                source="ai_control",
                success=result.get("success", False),
                error_message=result.get("error", ""),
                risk_level=result.get("risk_level", "low"),
                detail=str(result.get("target_label", "")),
            )
        except Exception as audit_err:
            import logging
            logging.getLogger(__name__).warning("审计日志写入失败: %s", audit_err)

    success_count = sum(1 for item in results if item.get("success"))
    failure_count = len(results) - success_count
    return {
        "success": failure_count == 0 and len(results) > 0,
        "risk_level": _merge_risk_levels(action_levels),
        "summary": (
            f"共处理 {len(results)} 条动作，成功 {success_count} 条，失败 {failure_count} 条。"
            if results else "没有可执行动作。"
        ),
        "results": results,
    }
