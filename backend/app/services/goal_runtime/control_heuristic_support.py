from __future__ import annotations

import re
from typing import Any


def priority_from_text(text: str) -> str | None:
    normalized = (text or "").lower()
    if "紧急" in normalized or "urgent" in normalized:
        return "urgent"
    if "可延迟" in normalized or "延迟" in normalized or "deferrable" in normalized:
        return "deferrable"
    if "普通" in normalized or "normal" in normalized:
        return "normal"
    return None


def priority_label(priority: str | None) -> str:
    return {
        "urgent": "紧急",
        "normal": "普通",
        "deferrable": "可延迟",
    }.get(priority or "", priority or "未知")


def find_pid(text: str) -> int | None:
    match = re.search(r"(?:pid|进程)\s*[:：]?\s*(\d+)", text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    standalone = re.search(r"\b(\d{3,7})\b", text)
    if standalone:
        return int(standalone.group(1))
    return None


def find_gpu_index(text: str) -> int | None:
    match = re.search(r"gpu\s*[:：]?\s*(\d+)", text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"显卡\s*[:：]?\s*(\d+)", text)
    if match:
        return int(match.group(1))
    return None


def find_power_limit(text: str) -> int | None:
    match = re.search(r"(\d{3})\s*w\b", text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d{3})\s*瓦", text)
    if match:
        return int(match.group(1))
    return None


def find_budget_value(text: str) -> int | None:
    match = re.search(
        r"(?:预算|总功率|功率预算).*?(\d{3,4})\s*(?:w|瓦)?",
        text,
        flags=re.IGNORECASE,
    )
    return int(match.group(1)) if match else None


def find_carbon_budget_value(text: str) -> float | None:
    match = re.search(
        r"(?:碳预算|carbon budget).*?(\d+(?:\.\d+)?)\s*(?:kg|公斤)",
        text,
        flags=re.IGNORECASE,
    )
    return float(match.group(1)) if match else None


def find_job_id(text: str) -> str | None:
    match = re.search(r"\b(job[-\w.]+)\b", text, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"作业\s*[:：]?\s*([a-z0-9][\w.-]*)", text, flags=re.IGNORECASE)
    return match.group(1) if match else None


def find_node_id(text: str) -> str | None:
    match = re.search(r"(?:节点|node)\s*[:：]?\s*([a-z0-9][\w.-]*)", text, flags=re.IGNORECASE)
    return match.group(1) if match else None


def find_allocation_id(text: str) -> str | None:
    match = re.search(r"\b(alloc[-\w.]+)\b", text, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"(?:allocation)\s*[:：]?\s*([a-z0-9][\w.-]*)", text, flags=re.IGNORECASE)
    return match.group(1) if match else None


def toggle_value(text: str, keywords: tuple[str, ...]) -> bool | None:
    lowered = (text or "").lower()
    if not any(keyword in lowered for keyword in keywords):
        return None
    if any(word in lowered for word in ("关闭", "禁用", "停用", "off", "disable")):
        return False
    if any(word in lowered for word in ("开启", "启用", "打开", "on", "enable")):
        return True
    return None


def build_auto_schedule_actions(text: str) -> list[dict[str, Any]]:
    auto_enabled = toggle_value(text, ("自动调度", "自动排程", "auto schedule"))
    if auto_enabled is None:
        return []
    return [
        {
            "action": "configure_auto_schedule",
            "target": {"enabled": auto_enabled},
            "reason": "根据用户指令调整自动调度开关",
        }
    ]


def build_schedule_once_actions(text: str) -> list[dict[str, Any]]:
    if not any(word in text for word in ("调度一次", "执行调度", "运行调度", "schedule once")):
        return []
    return [
        {
            "action": "run_schedule_once",
            "target": {},
            "reason": "根据用户指令手动执行一次综合调度",
        }
    ]


def build_carbon_budget_actions(text: str) -> list[dict[str, Any]]:
    carbon_budget = find_carbon_budget_value(text)
    if carbon_budget is None:
        return []
    return [
        {
            "action": "configure_carbon_budget",
            "target": {"enabled": True, "daily_budget_kg": carbon_budget},
            "reason": f"根据用户指令将每日碳预算设置为 {carbon_budget}kg",
        }
    ]


def build_budget_actions(text: str) -> list[dict[str, Any]]:
    budget_value = find_budget_value(text)
    if budget_value is None:
        return []
    return [
        {
            "action": "configure_budget",
            "target": {"enabled": True, "total_power_budget": budget_value},
            "reason": f"根据用户指令将总功率预算设置为 {budget_value}W",
        }
    ]


def build_gpu_power_actions(text: str) -> list[dict[str, Any]]:
    gpu_index = find_gpu_index(text)
    power_limit = find_power_limit(text)
    keywords = (
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
    if gpu_index is None or power_limit is None or not any(word in text for word in keywords):
        return []
    return [
        {
            "action": "set_power_limit",
            "target": {"gpu_index": gpu_index, "power_limit": power_limit},
            "reason": f"根据用户指令将 GPU {gpu_index} 的功耗上限设置为 {power_limit}W",
        }
    ]


def build_node_actions(text: str) -> list[dict[str, Any]]:
    node_id = find_node_id(text)
    if node_id is None:
        return []
    if any(word in text for word in ("排空节点", "drain node", "drain")):
        return [
            {
                "action": "drain_node",
                "target": {"node_id": node_id},
                "reason": f"根据用户指令将节点 {node_id} 标记为 drained",
            }
        ]
    if any(word in text for word in ("恢复节点", "取消排空", "undrain node", "undrain")):
        return [
            {
                "action": "undrain_node",
                "target": {"node_id": node_id},
                "reason": f"根据用户指令恢复节点 {node_id} 的调度状态",
            }
        ]
    return []


def build_allocation_actions(text: str) -> list[dict[str, Any]]:
    allocation_id = find_allocation_id(text)
    if allocation_id is None:
        return []
    keywords = ("释放 allocation", "释放分配", "release allocation", "release")
    if not any(word in text for word in keywords):
        return []
    return [
        {
            "action": "release_allocation",
            "target": {"allocation_id": allocation_id},
            "reason": f"根据用户指令释放 allocation {allocation_id}",
        }
    ]


def build_job_actions(text: str) -> list[dict[str, Any]]:
    job_id = find_job_id(text)
    if job_id is None:
        return []
    if any(word in text for word in ("暂停作业", "暂停 job", "pause job", "pause")):
        return [
            {
                "action": "pause_job",
                "target": {"job_id": job_id},
                "reason": f"根据用户指令暂停作业 {job_id}",
            }
        ]
    if any(word in text for word in ("恢复作业", "继续作业", "resume job", "resume")):
        return [
            {
                "action": "resume_job",
                "target": {"job_id": job_id},
                "reason": f"根据用户指令恢复作业 {job_id}",
            }
        ]
    if any(word in text for word in ("取消作业", "停止作业", "cancel job", "cancel")):
        return [
            {
                "action": "cancel_job",
                "target": {"job_id": job_id},
                "reason": f"根据用户指令取消作业 {job_id}",
            }
        ]
    return []


def build_task_actions(text: str) -> list[dict[str, Any]]:
    pid = find_pid(text)
    if pid is None:
        return []
    actions: list[dict[str, Any]] = []
    if any(word in text for word in ("暂停", "挂起", "pause")):
        actions.append(
            {
                "action": "pause_task",
                "target": {"pid": pid},
                "reason": f"根据用户指令暂停 PID {pid}",
            }
        )
    elif any(word in text for word in ("恢复", "继续", "resume")):
        actions.append(
            {
                "action": "resume_task",
                "target": {"pid": pid},
                "reason": f"根据用户指令恢复 PID {pid}",
            }
        )
    elif any(word in text for word in ("终止", "结束", "杀掉", "terminate", "kill")):
        actions.append(
            {
                "action": "terminate_task",
                "target": {"pid": pid},
                "reason": f"根据用户指令终止 PID {pid}",
            }
        )
    priority = priority_from_text(text)
    if priority is not None:
        actions.append(
            {
                "action": "set_task_priority",
                "target": {"pid": pid, "priority": priority},
                "reason": f"根据用户指令把 PID {pid} 调整为 {priority_label(priority)}",
            }
        )
    return actions
