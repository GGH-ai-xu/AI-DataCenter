"""图谱支撑的优化策略与代码模板生成。"""

from __future__ import annotations

import json
from typing import Any

from app.services.graph_qa import build_graph_answer_context
from app.services.optimization_ontology import get_graph_mode_config


OPTIMIZATION_LABELS = set(get_graph_mode_config("optimization")["node_merge_keys"].keys())


def _count_items(items: list[dict[str, Any]], field: str, fallback: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = str(item.get(field) or fallback)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _filter_optimization_graph_view(graph_view: dict[str, Any]) -> dict[str, Any]:
    nodes = [node for node in list(graph_view.get("nodes") or []) if str(node.get("label") or "") in OPTIMIZATION_LABELS]
    if not nodes:
        return graph_view
    node_ids = {str(node.get("id") or "") for node in nodes}
    relationships = [
        relationship for relationship in list(graph_view.get("relationships") or [])
        if str(relationship.get("source_id") or "") in node_ids
        and str(relationship.get("target_id") or "") in node_ids
    ]
    return {
        **graph_view,
        "nodes": nodes,
        "relationships": relationships,
        "label_counts": _count_items(nodes, "label", "Unknown"),
        "relation_type_counts": _count_items(relationships, "type", "UNKNOWN"),
    }


def _pick_names(nodes: list[dict[str, Any]], label: str, limit: int = 3) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for node in nodes:
        if str(node.get("label") or "") != label:
            continue
        name = str(node.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
        if len(names) >= limit:
            break
    return names


def _parse_runtime_context(control_context: dict[str, Any]) -> dict[str, Any]:
    raw = control_context.get("llm_context")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    if isinstance(raw, dict):
        return raw
    return {}


def _runtime_summary_text(runtime_context: dict[str, Any]) -> str:
    gpus = list(runtime_context.get("gpus") or [])
    processes = list(runtime_context.get("manageable_processes") or [])
    budget = runtime_context.get("budget") or {}
    total_power = round(sum(float(item.get("power_usage", 0) or 0) for item in gpus), 1)
    avg_util = round(
        sum(float(item.get("gpu_utilization", 0) or 0) for item in gpus) / max(len(gpus), 1),
        1,
    ) if gpus else 0.0
    return (
        f"时段：{runtime_context.get('time_period') or '未知'}\n"
        f"GPU 数量：{len(gpus)}\n"
        f"可治理任务数：{len(processes)}\n"
        f"当前总功耗：{total_power}W\n"
        f"平均 GPU 利用率：{avg_util}%\n"
        f"预算状态：{json.dumps(budget, ensure_ascii=False)}"
    )


def build_graph_strategy_context(
    goal: str,
    graph_view: dict[str, Any],
    control_context: dict[str, Any],
    max_nodes: int = 10,
    max_relationships: int = 12,
) -> dict[str, Any]:
    filtered_graph = _filter_optimization_graph_view(graph_view)
    answer_context = build_graph_answer_context(
        goal,
        filtered_graph,
        max_nodes=max_nodes,
        max_relationships=max_relationships,
    )
    evidence_nodes = list(answer_context.get("evidence_nodes") or [])
    runtime_context = _parse_runtime_context(control_context)
    focus = {
        "strategies": _pick_names(evidence_nodes, "OptimizationStrategy"),
        "constraints": _pick_names(evidence_nodes, "Constraint"),
        "policies": _pick_names(evidence_nodes, "Policy"),
        "metrics": _pick_names(evidence_nodes, "Metric"),
        "templates": _pick_names(evidence_nodes, "CodeTemplate"),
        "apis": _pick_names(evidence_nodes, "API"),
        "periods": _pick_names(evidence_nodes, "TimePeriod"),
        "task_types": _pick_names(evidence_nodes, "TaskType"),
    }
    context_text = (
        f"优化目标：{goal.strip()}\n\n"
        f"图谱证据：\n{answer_context['context_text']}\n\n"
        f"当前运行态：\n{_runtime_summary_text(runtime_context)}"
    )
    return {
        "goal": goal.strip(),
        "graph_view": filtered_graph,
        "runtime_context": runtime_context,
        "runtime_summary": _runtime_summary_text(runtime_context),
        "focus": focus,
        "context_text": context_text,
        **answer_context,
    }


def build_graph_strategy_fallback(goal: str, context: dict[str, Any]) -> dict[str, Any]:
    focus = dict(context.get("focus") or {})
    strategies = list(focus.get("strategies") or [])
    constraints = list(focus.get("constraints") or [])
    metrics = list(focus.get("metrics") or [])
    templates = list(focus.get("templates") or [])
    apis = list(focus.get("apis") or [])
    periods = list(focus.get("periods") or [])
    task_types = list(focus.get("task_types") or [])
    runtime_context = dict(context.get("runtime_context") or {})
    time_period = runtime_context.get("time_period") or (periods[0] if periods else "当前时段")

    summary_parts = []
    if strategies:
        summary_parts.append(f"图谱建议以“{strategies[0]}”作为主策略")
    if constraints:
        summary_parts.append(f"并优先满足“{constraints[0]}”")
    if metrics:
        summary_parts.append(f"重点守住“{' / '.join(metrics[:2])}”")
    summary = "，".join(summary_parts) if summary_parts else "当前图谱证据还不够完整，建议先按保守策略生成方案。"

    steps: list[str] = []
    if periods:
        steps.append(f"先按“{periods[0]}”的运行场景组织治理动作。")
    else:
        steps.append(f"先结合 {time_period} 的运行态判断是否需要启用保守限功。")
    if constraints:
        steps.append(f"在所有动作前先锁定约束：{constraints[0]}。")
    elif task_types:
        steps.append(f"优先保护 {task_types[0]}，避免直接影响关键业务。")
    if strategies:
        steps.append(f"主策略采用“{strategies[0]}”，逐步调整功率、优先级和调度顺序。")
    else:
        steps.append("优先对低利用率 GPU 做小步限功，对可延迟任务做排序或降级。")
    if metrics:
        steps.append(f"重点观察 {metrics[0]}，同时兼顾 {' / '.join(metrics[1:2]) or '任务时效'}。")
    if templates or apis:
        template_text = templates[0] if templates else "当前治理模板"
        api_text = " / ".join(apis[:3]) if apis else "set_power_limit / set_task_priority / run_schedule_once"
        steps.append(f"代码层复用“{template_text}”，优先调用 {api_text} 这类已有接口。")
    steps.append("生成计划后先在执行控制台做人工确认，再落到真实设备。")
    strategy_steps = steps[:6]

    code_title = templates[0] if templates else (strategies[0] if strategies else "graph_guarded_strategy")
    api_names = apis[:3]
    while len(api_names) < 3:
        api_names.append(["set_power_limit", "set_task_priority", "run_schedule_once"][len(api_names)])
    code_snippet = "\n".join([
        f"def {str(code_title).replace('-', '_').replace(' ', '_').lower()}(gpus, tasks, budget_status):",
        f"    \"\"\"{goal.strip() or 'GraphRAG 约束驱动优化模板'}\"\"\"",
        "    urgent_tasks = [task for task in tasks if task.get('priority') == 'urgent']",
        "    deferrable_tasks = [task for task in tasks if task.get('priority') == 'deferrable']",
        "    total_power = sum(float(gpu.get('power_usage', 0) or 0) for gpu in gpus)",
        "    target_gpus = [",
        "        gpu for gpu in gpus",
        "        if float(gpu.get('gpu_utilization', 0) or 0) < 40 and float(gpu.get('temperature', 0) or 0) < 85",
        "    ]",
        "    if budget_status.get('enabled') and total_power >= float(budget_status.get('total_power_budget', 0) or 0):",
        f"        for gpu in target_gpus:",
        f"            {api_names[0]}(gpu['index'], 220)",
        "        for task in deferrable_tasks:",
        f"            {api_names[1]}(task['pid'], 'deferrable')",
        f"        {api_names[2]}()",
        "    return {",
        "        'protected_urgent_tasks': len(urgent_tasks),",
        "        'adjusted_gpu_count': len(target_gpus),",
        "        'deferred_task_count': len(deferrable_tasks),",
        "    }",
    ])

    control_prompt = (
        f"基于当前图谱先执行一版保守优化：在{time_period}优先保护"
        f"{constraints[0] if constraints else (task_types[0] if task_types else '紧急任务')}"
        "，对低利用率 GPU 小步限功到 220W，并对可延迟任务做排序后执行一次综合调度。"
    )

    follow_ups = list(context.get("follow_ups") or [])[:4]
    if not follow_ups:
        follow_ups = [
            "这套策略依赖了哪些约束和模板？",
            "当前图谱里还有哪些 API 可以接进代码模板？",
        ]

    return {
        "summary": summary,
        "strategy_steps": strategy_steps,
        "control_prompt": control_prompt,
        "code_title": code_title,
        "code_language": "python",
        "code_snippet": code_snippet,
        "risk_notice": "这是一版图谱支撑的保守模板，真正执行前仍应在控制台核对 GPU、任务和预算状态。",
        "evidence": list(context.get("evidence_lines") or [])[:6],
        "follow_ups": follow_ups,
    }
