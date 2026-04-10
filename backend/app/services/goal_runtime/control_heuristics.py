from __future__ import annotations

import re
from typing import Any


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
    match = re.search(
        r"(?:预算|总功率|功率预算).*?(\d{3,4})\s*(?:w|瓦)?",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return int(match.group(1))
    return None


def _risk_level(action_name: str) -> str:
    return "high" if action_name in HIGH_RISK_ACTIONS else "medium"


def build_control_heuristic(message: str) -> dict:
    text = (message or "").strip()
    lowered = text.lower()
    actions: list[dict] = []
    warnings: list[str] = []

    if any(word in lowered for word in ("调度一次", "执行调度", "运行调度", "schedule once")):
        actions.append(
            {
                "action": "run_schedule_once",
                "target": {},
                "reason": "根据用户指令手动执行一次综合调度",
            }
        )

    budget_value = _find_budget_value(lowered)
    if budget_value is not None:
        actions.append(
            {
                "action": "configure_budget",
                "target": {"enabled": True, "total_power_budget": budget_value},
                "reason": f"根据用户指令将总功率预算设置为 {budget_value}W",
            }
        )

    gpu_index = _find_gpu_index(lowered)
    power_limit = _find_power_limit(lowered)
    if gpu_index is not None and power_limit is not None and any(
        word in lowered
        for word in (
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
        actions.append(
            {
                "action": "set_power_limit",
                "target": {"gpu_index": gpu_index, "power_limit": power_limit},
                "reason": f"根据用户指令将 GPU {gpu_index} 的功耗上限设置为 {power_limit}W",
            }
        )

    pid = _find_pid(lowered)
    if pid is not None:
        if any(word in lowered for word in ("暂停", "挂起", "pause")):
            actions.append(
                {
                    "action": "pause_task",
                    "target": {"pid": pid},
                    "reason": f"根据用户指令暂停 PID {pid}",
                }
            )
        elif any(word in lowered for word in ("恢复", "继续", "resume")):
            actions.append(
                {
                    "action": "resume_task",
                    "target": {"pid": pid},
                    "reason": f"根据用户指令恢复 PID {pid}",
                }
            )
        elif any(word in lowered for word in ("终止", "结束", "杀掉", "terminate", "kill")):
            actions.append(
                {
                    "action": "terminate_task",
                    "target": {"pid": pid},
                    "reason": f"根据用户指令终止 PID {pid}",
                }
            )

        priority = _priority_from_text(lowered)
        if priority:
            actions.append(
                {
                    "action": "set_task_priority",
                    "target": {"pid": pid, "priority": priority},
                    "reason": f"根据用户指令把 PID {pid} 调整为 {_priority_label(priority)}",
                }
            )

    if not actions:
        warnings.append("暂时无法从这句话中提取可执行动作，请明确给出 PID、GPU 编号或预算值。")

    return {
        "planner": "rule",
        "summary": "已按规则解析用户指令并生成执行计划。" if actions else "暂时无法解析成可执行动作。",
        "risk_level": "high" if any(item["action"] in HIGH_RISK_ACTIONS for item in actions) else "medium",
        "requires_confirmation": any(item["action"] in HIGH_RISK_ACTIONS for item in actions),
        "warnings": warnings,
        "actions": actions,
    }
