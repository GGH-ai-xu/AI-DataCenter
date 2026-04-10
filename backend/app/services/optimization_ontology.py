"""图谱模式与智算中心优化本体定义。"""

from __future__ import annotations

from typing import Any


DEFAULT_GRAPH_MODE = "paper"


GRAPH_MODE_SOURCE_DEFAULTS = {
    "paper": "paper",
    "optimization": "optimization",
}


GRAPH_MODE_SOURCE_TYPE_DEFAULTS = {
    "paper": "paper",
    "optimization": "rule",
}


GRAPH_LABEL_PRIORITY = {
    "Paper": 0,
    "Policy": 1,
    "OptimizationStrategy": 2,
    "Constraint": 3,
    "PowerBudget": 4,
    "CarbonTarget": 5,
    "TaskType": 6,
    "TimePeriod": 7,
    "Metric": 8,
    "CodeTemplate": 9,
    "API": 10,
    "Cluster": 11,
    "GPU": 12,
    "Task": 13,
    "Method": 14,
    "Dataset": 15,
    "Action": 16,
}


def _normalize_key(value: Any) -> str:
    chars: list[str] = []
    last_space = False
    for ch in str(value or "").strip().lower():
        if ch.isalnum():
            chars.append(ch)
            last_space = False
        else:
            if not last_space:
                chars.append(" ")
            last_space = True
    return "".join(chars).strip()


def _build_alias_map(entries: dict[str, list[str]]) -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for canonical, aliases in entries.items():
        for alias in aliases:
            normalized = _normalize_key(alias)
            if normalized:
                alias_map[normalized] = canonical
    return alias_map


PAPER_NODE_LABELS = _build_alias_map({
    "Paper": ["Paper", "paper", "论文"],
    "Method": ["Method", "method", "方法"],
    "Task": ["Task", "task", "任务"],
    "Dataset": ["Dataset", "dataset", "数据集"],
    "Metric": ["Metric", "metric", "指标"],
})


PAPER_RELATION_TYPES = _build_alias_map({
    "PROPOSES": ["PROPOSES", "proposes", "提出"],
    "SOLVES": ["SOLVES", "solves", "解决"],
    "USES": ["USES", "uses", "使用", "依赖"],
    "ACHIEVES": ["ACHIEVES", "achieves", "达到", "提升"],
})


PAPER_NODE_MERGE_KEYS = {
    "Paper": ("name",),
    "Method": ("name",),
    "Task": ("name",),
    "Dataset": ("name",),
    "Metric": ("name",),
}


PAPER_NODE_NAME_ALIASES = {
    "Method": {
        _normalize_key("retrieval augmented generation"): "Retrieval-Augmented Generation (RAG)",
        _normalize_key("retrieval augmented generation rag"): "Retrieval-Augmented Generation (RAG)",
        _normalize_key("retrieval augmented generation rag model"): "Retrieval-Augmented Generation (RAG)",
        _normalize_key("rag"): "Retrieval-Augmented Generation (RAG)",
        _normalize_key("graph rag"): "GraphRAG",
        _normalize_key("self rag"): "Self-RAG (Self-Reflective Retrieval-Augmented Generation)",
        _normalize_key("rag sequence"): "RAG-Sequence",
        _normalize_key("rag token"): "RAG-Token",
    },
    "Task": {
        _normalize_key("open domain qa"): "Open-Domain Question Answering (Open-Domain QA)",
        _normalize_key("open domain question answering"): "Open-Domain Question Answering (Open-Domain QA)",
        _normalize_key("open domain question answering open domain qa"): "Open-Domain Question Answering (Open-Domain QA)",
        _normalize_key("query focused summarization"): "Query-Focused Summarization",
        _normalize_key("language generation tasks"): "Language Generation",
    },
    "Dataset": {
        _normalize_key("wikipedia corpus"): "Wikipedia",
        _normalize_key("wikipedia passages"): "Wikipedia",
    },
}


PAPER_SUPPORTING_DEPENDENCIES = {
    "GraphRAG": ["Retrieval-Augmented Generation (RAG)"],
    "Self-RAG (Self-Reflective Retrieval-Augmented Generation)": ["Retrieval-Augmented Generation (RAG)"],
    "RAG-Sequence": ["Retrieval-Augmented Generation (RAG)"],
    "RAG-Token": ["Retrieval-Augmented Generation (RAG)"],
}


OPTIMIZATION_NODE_LABELS = _build_alias_map({
    "Cluster": ["Cluster", "cluster", "集群"],
    "GPU": ["GPU", "gpu", "显卡"],
    "Task": ["Task", "task", "任务"],
    "TaskType": ["TaskType", "task type", "task_type", "任务类型"],
    "TimePeriod": ["TimePeriod", "time period", "time_period", "时段", "时间段"],
    "Constraint": ["Constraint", "constraint", "约束"],
    "PowerBudget": ["PowerBudget", "power budget", "power_budget", "功率预算", "功耗预算"],
    "CarbonTarget": ["CarbonTarget", "carbon target", "carbon_target", "碳目标", "碳预算"],
    "Policy": ["Policy", "policy", "策略总则", "治理策略", "策略"],
    "OptimizationStrategy": [
        "OptimizationStrategy",
        "optimization strategy",
        "optimization_strategy",
        "strategy",
        "调度策略",
        "优化策略",
    ],
    "Metric": ["Metric", "metric", "指标"],
    "CodeTemplate": ["CodeTemplate", "code template", "code_template", "template", "代码模板", "模板"],
    "API": ["API", "api", "接口"],
    "Action": ["Action", "action", "动作"],
})


OPTIMIZATION_RELATION_TYPES = _build_alias_map({
    "RUNS_ON": ["RUNS_ON", "runs on", "部署于", "运行于"],
    "BELONGS_TO": ["BELONGS_TO", "belongs to", "属于"],
    "CONSTRAINS": ["CONSTRAINS", "constrains", "约束"],
    "APPLIES_TO": ["APPLIES_TO", "applies to", "适用于"],
    "OPTIMIZES": ["OPTIMIZES", "optimizes", "优化"],
    "LIMITS": ["LIMITS", "limits", "限制"],
    "USES_TEMPLATE": ["USES_TEMPLATE", "uses template", "uses_template", "使用模板"],
    "CALLS_API": ["CALLS_API", "calls api", "calls_api", "调用接口"],
    "AFFECTS": ["AFFECTS", "affects", "影响"],
    "TRIGGERS": ["TRIGGERS", "triggers", "触发"],
    "REQUIRES": ["REQUIRES", "requires", "依赖"],
    "USES": ["USES", "uses", "使用"],
})


OPTIMIZATION_NODE_MERGE_KEYS = {
    "Cluster": ("name",),
    "GPU": ("name",),
    "Task": ("name",),
    "TaskType": ("name",),
    "TimePeriod": ("name",),
    "Constraint": ("name",),
    "PowerBudget": ("name",),
    "CarbonTarget": ("name",),
    "Policy": ("name",),
    "OptimizationStrategy": ("name",),
    "Metric": ("name",),
    "CodeTemplate": ("name",),
    "API": ("name",),
    "Action": ("name",),
}


OPTIMIZATION_NODE_NAME_ALIASES = {
    "TimePeriod": {
        _normalize_key("peak hours"): "高峰期",
        _normalize_key("peak period"): "高峰期",
        _normalize_key("off peak"): "低谷期",
        _normalize_key("off peak hours"): "低谷期",
    },
    "TaskType": {
        _normalize_key("urgent"): "紧急任务",
        _normalize_key("critical"): "紧急任务",
        _normalize_key("deferrable"): "可延迟任务",
        _normalize_key("delayable"): "可延迟任务",
        _normalize_key("normal"): "普通任务",
    },
    "Metric": {
        _normalize_key("total power"): "总功耗",
        _normalize_key("power consumption"): "总功耗",
        _normalize_key("sla"): "任务时效",
        _normalize_key("response latency"): "响应时延",
        _normalize_key("carbon emission"): "碳排放",
    },
}


GRAPH_MODE_CONFIGS = {
    "paper": {
        "display_name": "论文知识图谱",
        "allowed_node_labels": PAPER_NODE_LABELS,
        "allowed_relation_types": PAPER_RELATION_TYPES,
        "node_merge_keys": PAPER_NODE_MERGE_KEYS,
        "node_name_aliases": PAPER_NODE_NAME_ALIASES,
        "supporting_dependencies": PAPER_SUPPORTING_DEPENDENCIES,
        "dependency_source_labels": {"Method"},
        "node_order": ["Paper", "Method", "Task", "Dataset", "Metric"],
        "relation_order": ["PROPOSES", "SOLVES", "USES", "ACHIEVES"],
        "root_requirement": "必须包含一个 Paper 节点，并让其他节点围绕它展开。",
        "mode_instruction": "优先抽取论文里的方法、任务、数据集和指标，不要把背景句子拆成无意义节点。",
    },
    "optimization": {
        "display_name": "智算中心优化本体图谱",
        "allowed_node_labels": OPTIMIZATION_NODE_LABELS,
        "allowed_relation_types": OPTIMIZATION_RELATION_TYPES,
        "node_merge_keys": OPTIMIZATION_NODE_MERGE_KEYS,
        "node_name_aliases": OPTIMIZATION_NODE_NAME_ALIASES,
        "supporting_dependencies": {},
        "dependency_source_labels": set(),
        "node_order": [
            "Policy",
            "OptimizationStrategy",
            "Constraint",
            "PowerBudget",
            "CarbonTarget",
            "TaskType",
            "TimePeriod",
            "Metric",
            "CodeTemplate",
            "API",
            "Cluster",
            "GPU",
            "Task",
            "Action",
        ],
        "relation_order": [
            "CONSTRAINS",
            "APPLIES_TO",
            "OPTIMIZES",
            "LIMITS",
            "USES_TEMPLATE",
            "CALLS_API",
            "TRIGGERS",
            "REQUIRES",
            "AFFECTS",
            "BELONGS_TO",
            "RUNS_ON",
            "USES",
        ],
        "root_requirement": "至少包含一个 Policy、OptimizationStrategy、Constraint 或 CodeTemplate 节点。",
        "mode_instruction": (
            "把文本理解为智算中心优化知识，只抽取可落地的约束、策略、预算、时段、指标、模板和接口。"
            "不要把口号、形容词或泛泛而谈的句子当成节点。"
        ),
    },
}


def normalize_graph_mode(value: Any) -> str:
    normalized = _normalize_key(value)
    if normalized in {"optimization", "opt", "ontology", "graph rag", "优化", "本体"}:
        return "optimization"
    return DEFAULT_GRAPH_MODE


def graph_source_default(mode: Any) -> str:
    return GRAPH_MODE_SOURCE_DEFAULTS[normalize_graph_mode(mode)]


def graph_source_type_default(mode: Any) -> str:
    return GRAPH_MODE_SOURCE_TYPE_DEFAULTS[normalize_graph_mode(mode)]


def get_graph_mode_config(mode: Any) -> dict[str, Any]:
    normalized = normalize_graph_mode(mode)
    return GRAPH_MODE_CONFIGS[normalized]


def build_graph_extract_prompt(mode: Any) -> str:
    normalized = normalize_graph_mode(mode)
    config = get_graph_mode_config(normalized)
    node_lines = "\n".join(f"- {label}" for label in config["node_order"])
    relation_lines = "\n".join(f"- {relation}" for relation in config["relation_order"])
    return f"""你是知识图谱抽取助手。你的任务是把论文、规则、策略说明或技术资料整理成固定结构的图谱草稿。

当前模式：{config['display_name']}

只允许以下节点类型：
{node_lines}

只允许以下关系类型：
{relation_lines}

额外约束：
1. {config['mode_instruction']}
2. {config['root_requirement']}
3. 输出只返回 JSON，不要返回 Markdown，不要解释。
4. 节点字段只允许：id, label, name, description, source_type, domain_tag, scenario
5. 关系字段只允许：from_id, to_id, type, description, source_type, domain_tag, scenario
6. 如果信息不足，不要编造；可以减少节点和关系数量。

返回格式：
{{
  "nodes": [
    {{"id": "node_1", "label": "{config['node_order'][0]}", "name": "节点名称", "description": "一句话说明"}}
  ],
  "relations": [
    {{"from_id": "node_1", "to_id": "node_2", "type": "{config['relation_order'][0]}", "description": "关系说明"}}
  ]
}}"""
