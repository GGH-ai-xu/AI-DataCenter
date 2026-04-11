from __future__ import annotations

from app.services.goal_runtime.cluster_execution_heuristics import (
    build_cluster_execution_actions,
)
from app.services.goal_runtime.job_submit_heuristics import (
    build_submit_job_actions,
)
from app.services.goal_runtime.job_control_heuristics import (
    build_job_control_actions,
)
from app.services.goal_runtime.cluster_planning_heuristics import (
    build_cluster_planning_actions,
)
from app.services.goal_runtime.control_heuristic_support import (
    build_allocation_actions,
    build_auto_schedule_actions,
    build_budget_actions,
    build_carbon_budget_actions,
    build_gpu_power_actions,
    build_job_actions,
    build_node_actions,
    build_schedule_once_actions,
    build_task_actions,
)


HIGH_RISK_ACTIONS = {"terminate_task", "cancel_job"}


def build_control_heuristic(message: str) -> dict:
    text = (message or "").strip().lower()
    actions = [
        *build_cluster_planning_actions(text),
        *build_cluster_execution_actions(text),
        *build_submit_job_actions(text),
        *build_job_control_actions(text),
        *build_auto_schedule_actions(text),
        *build_schedule_once_actions(text),
        *build_carbon_budget_actions(text),
        *build_node_actions(text),
        *build_allocation_actions(text),
        *build_budget_actions(text),
        *build_gpu_power_actions(text),
        *build_job_actions(text),
        *build_task_actions(text),
    ]
    warnings = []
    if not actions:
        warnings.append("暂时无法从这句话中提取可执行动作，请明确给出 PID、GPU 编号、作业 ID 或预算值。")
    requires_confirmation = any(item["action"] in HIGH_RISK_ACTIONS for item in actions)
    return {
        "planner": "rule",
        "summary": "已按规则解析用户指令并生成执行计划。" if actions else "暂时无法解析成可执行动作。",
        "risk_level": "high" if requires_confirmation else "medium",
        "requires_confirmation": requires_confirmation,
        "warnings": warnings,
        "actions": actions,
    }
