"""内置演示图库：论文图与优化本体图。"""

from __future__ import annotations


PAPER_DEMO_GRAPH = {
    "title": "GraphRAG 论文演示图",
    "mode": "paper",
    "source": "paper",
    "source_type": "paper",
    "domain_tag": "GraphRAG",
    "scenario": "项目场景展示",
    "nodes": [
        {"id": "paper_rag", "label": "Paper", "name": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks", "description": "RAG 论文，提出检索增强生成范式。"},
        {"id": "paper_self_rag", "label": "Paper", "name": "Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection", "description": "Self-RAG 论文，引入自反思检索增强生成。"},
        {"id": "paper_graphrag", "label": "Paper", "name": "From Local to Global: A Graph RAG Approach to Query-Focused Summarization", "description": "GraphRAG 论文，将图结构引入检索增强问答。"},
        {"id": "method_rag", "label": "Method", "name": "Retrieval-Augmented Generation (RAG)", "description": "基础检索增强生成方法。"},
        {"id": "method_self_rag", "label": "Method", "name": "Self-RAG (Self-Reflective Retrieval-Augmented Generation)", "description": "可按需检索并带自反思的 RAG。"},
        {"id": "method_graphrag", "label": "Method", "name": "GraphRAG", "description": "基于图结构和社区摘要的 RAG 方法。"},
        {"id": "task_qa", "label": "Task", "name": "Open-Domain Question Answering (Open-Domain QA)", "description": "开放域问答任务。"},
        {"id": "task_generation", "label": "Task", "name": "Language Generation", "description": "语言生成任务。"},
        {"id": "task_fact", "label": "Task", "name": "Fact Verification", "description": "事实核验任务。"},
        {"id": "task_summary", "label": "Task", "name": "Query-Focused Summarization", "description": "面向查询的摘要任务。"},
        {"id": "dataset_wiki", "label": "Dataset", "name": "Wikipedia", "description": "Wikipedia 语料库。"},
        {"id": "dataset_private", "label": "Dataset", "name": "Private Text Corpora", "description": "私有文本语料集合。"},
        {"id": "metric_factuality", "label": "Metric", "name": "Factuality", "description": "回答事实性。"},
        {"id": "metric_citation", "label": "Metric", "name": "Citation Accuracy", "description": "引用准确性。"},
        {"id": "metric_comprehensiveness", "label": "Metric", "name": "Comprehensiveness", "description": "回答完整性。"},
        {"id": "metric_diversity", "label": "Metric", "name": "Diversity", "description": "回答多样性。"},
    ],
    "relations": [
        {"from_id": "paper_rag", "to_id": "method_rag", "type": "PROPOSES", "description": "RAG 论文提出基础检索增强生成方法。"},
        {"from_id": "method_rag", "to_id": "task_qa", "type": "SOLVES", "description": "RAG 面向开放域问答。"},
        {"from_id": "method_rag", "to_id": "task_generation", "type": "SOLVES", "description": "RAG 同时可用于语言生成。"},
        {"from_id": "method_rag", "to_id": "dataset_wiki", "type": "USES", "description": "RAG 使用 Wikipedia 作为外部知识。"},
        {"from_id": "paper_self_rag", "to_id": "method_self_rag", "type": "PROPOSES", "description": "Self-RAG 论文提出自反思 RAG。"},
        {"from_id": "method_self_rag", "to_id": "method_rag", "type": "USES", "description": "Self-RAG 建立在基础 RAG 范式之上。"},
        {"from_id": "method_self_rag", "to_id": "task_qa", "type": "SOLVES", "description": "Self-RAG 用于开放域问答。"},
        {"from_id": "method_self_rag", "to_id": "task_fact", "type": "SOLVES", "description": "Self-RAG 适用于事实核验任务。"},
        {"from_id": "method_self_rag", "to_id": "metric_factuality", "type": "ACHIEVES", "description": "Self-RAG 提升回答事实性。"},
        {"from_id": "method_self_rag", "to_id": "metric_citation", "type": "ACHIEVES", "description": "Self-RAG 提升引用准确性。"},
        {"from_id": "paper_graphrag", "to_id": "method_graphrag", "type": "PROPOSES", "description": "GraphRAG 论文提出图结构 RAG。"},
        {"from_id": "method_graphrag", "to_id": "method_rag", "type": "USES", "description": "GraphRAG 延续 RAG 的外部检索范式。"},
        {"from_id": "method_graphrag", "to_id": "task_summary", "type": "SOLVES", "description": "GraphRAG 面向查询聚焦摘要。"},
        {"from_id": "method_graphrag", "to_id": "dataset_private", "type": "USES", "description": "GraphRAG 服务于私有文本语料。"},
        {"from_id": "method_graphrag", "to_id": "metric_comprehensiveness", "type": "ACHIEVES", "description": "GraphRAG 提升回答完整性。"},
        {"from_id": "method_graphrag", "to_id": "metric_diversity", "type": "ACHIEVES", "description": "GraphRAG 提升回答多样性。"},
    ],
}


OPTIMIZATION_DEMO_GRAPH = {
    "title": "绿算生金智算中心优化本体演示图",
    "mode": "optimization",
    "source": "optimization",
    "source_type": "rule",
    "domain_tag": "智算中心优化",
    "scenario": "项目场景展示",
    "nodes": [
        {"id": "policy_1", "label": "Policy", "name": "三层调度总则", "description": "规则引擎保底线，预算引擎控成本，AI 引擎做全局优化。"},
        {"id": "constraint_1", "label": "Constraint", "name": "紧急任务不可暂停", "description": "urgent 任务不能被 pause 或强行降级，是治理底线。"},
        {"id": "constraint_2", "label": "Constraint", "name": "高温优先降功率", "description": "温度超过阈值时，优先通过降功率保护设备安全。"},
        {"id": "budget_1", "label": "PowerBudget", "name": "集群总功率预算", "description": "当机房功率接近上限时，需要通过预算约束触发调度。"},
        {"id": "carbon_1", "label": "CarbonTarget", "name": "日碳排预算", "description": "平台需要在日尺度上控制碳排放与能耗支出。"},
        {"id": "period_1", "label": "TimePeriod", "name": "高峰期", "description": "高峰期策略强调削峰和紧急任务保护。"},
        {"id": "period_2", "label": "TimePeriod", "name": "低谷期", "description": "低谷期策略强调恢复算力和补齐积压任务。"},
        {"id": "type_1", "label": "TaskType", "name": "紧急任务", "description": "必须保障时效与可用性，不能被暂停。"},
        {"id": "type_2", "label": "TaskType", "name": "可延迟任务", "description": "可以在高峰期被延后、降功率或重新排序。"},
        {"id": "metric_1", "label": "Metric", "name": "总功耗", "description": "平台重点优化的能耗指标。"},
        {"id": "metric_2", "label": "Metric", "name": "任务时效", "description": "紧急任务的 SLA 和完成时效必须被保护。"},
        {"id": "metric_3", "label": "Metric", "name": "碳排放", "description": "用于衡量节能和低碳治理效果。"},
        {"id": "strategy_1", "label": "OptimizationStrategy", "name": "高峰限功调度", "description": "在高峰期优先降低低负载 GPU 功率，并保护紧急任务。"},
        {"id": "strategy_2", "label": "OptimizationStrategy", "name": "低谷恢复调度", "description": "在低谷期恢复功率限制并继续执行积压任务。"},
        {"id": "strategy_3", "label": "OptimizationStrategy", "name": "预算触发调度", "description": "当总功率或碳预算逼近阈值时触发一次调度。"},
        {"id": "template_1", "label": "CodeTemplate", "name": "scheduler_power_guard", "description": "保护紧急任务前提下执行限功策略的代码模板。"},
        {"id": "template_2", "label": "CodeTemplate", "name": "budget_guardrail_runner", "description": "预算触发后执行调度与回滚提示的代码模板。"},
        {"id": "api_1", "label": "API", "name": "set_power_limit", "description": "设置 GPU 功率上限的执行接口。"},
        {"id": "api_2", "label": "API", "name": "run_schedule_once", "description": "执行一次调度的控制接口。"},
        {"id": "api_3", "label": "API", "name": "set_task_priority", "description": "调整任务优先级的接口。"},
        {"id": "cluster_1", "label": "Cluster", "name": "共享 GPU 集群", "description": "当前治理平台服务的共享 GPU 资源池。"},
    ],
    "relations": [
        {"from_id": "policy_1", "to_id": "constraint_1", "type": "CONSTRAINS", "description": "总则明确紧急任务保护底线。"},
        {"from_id": "policy_1", "to_id": "constraint_2", "type": "CONSTRAINS", "description": "总则要求高温时优先安全降功率。"},
        {"from_id": "policy_1", "to_id": "strategy_1", "type": "TRIGGERS", "description": "高峰期触发限功调度。"},
        {"from_id": "policy_1", "to_id": "strategy_3", "type": "TRIGGERS", "description": "预算逼近阈值时触发调度。"},
        {"from_id": "constraint_1", "to_id": "type_1", "type": "CONSTRAINS", "description": "紧急任务不可暂停。"},
        {"from_id": "constraint_2", "to_id": "cluster_1", "type": "CONSTRAINS", "description": "高温时需要保护集群设备。"},
        {"from_id": "budget_1", "to_id": "cluster_1", "type": "LIMITS", "description": "总功率预算约束集群上限。"},
        {"from_id": "carbon_1", "to_id": "cluster_1", "type": "LIMITS", "description": "碳预算限制集群长期排放。"},
        {"from_id": "strategy_1", "to_id": "period_1", "type": "APPLIES_TO", "description": "高峰限功调度适用于高峰期。"},
        {"from_id": "strategy_2", "to_id": "period_2", "type": "APPLIES_TO", "description": "低谷恢复调度适用于低谷期。"},
        {"from_id": "strategy_3", "to_id": "budget_1", "type": "REQUIRES", "description": "预算触发调度依赖功率预算阈值。"},
        {"from_id": "strategy_1", "to_id": "constraint_1", "type": "REQUIRES", "description": "限功策略必须服从紧急任务保护约束。"},
        {"from_id": "strategy_1", "to_id": "type_2", "type": "APPLIES_TO", "description": "高峰期优先处理可延迟任务。"},
        {"from_id": "strategy_1", "to_id": "metric_1", "type": "OPTIMIZES", "description": "目标是压低总功耗。"},
        {"from_id": "strategy_1", "to_id": "metric_2", "type": "AFFECTS", "description": "需要避免破坏紧急任务时效。"},
        {"from_id": "strategy_2", "to_id": "metric_2", "type": "OPTIMIZES", "description": "低谷期恢复算力以补齐任务时效。"},
        {"from_id": "strategy_3", "to_id": "metric_3", "type": "OPTIMIZES", "description": "预算触发调度服务于碳排和能耗目标。"},
        {"from_id": "strategy_1", "to_id": "template_1", "type": "USES_TEMPLATE", "description": "高峰限功调度依赖保护模板。"},
        {"from_id": "strategy_3", "to_id": "template_2", "type": "USES_TEMPLATE", "description": "预算触发调度依赖预算护栏模板。"},
        {"from_id": "template_1", "to_id": "api_1", "type": "CALLS_API", "description": "模板会调用限功接口。"},
        {"from_id": "template_1", "to_id": "api_3", "type": "CALLS_API", "description": "模板会调用任务优先级接口。"},
        {"from_id": "template_2", "to_id": "api_2", "type": "CALLS_API", "description": "模板会触发一次调度。"},
        {"from_id": "strategy_3", "to_id": "metric_1", "type": "OPTIMIZES", "description": "预算触发调度直接服务于总功耗控制。"},
        {"from_id": "strategy_3", "to_id": "constraint_1", "type": "REQUIRES", "description": "预算调度同样不能伤害紧急任务。"},
    ],
}


def list_graph_demo_kinds() -> list[str]:
    return ["paper", "optimization"]


def get_graph_demo_payload(kind: str) -> dict:
    normalized = str(kind or "").strip().lower()
    if normalized == "optimization":
        return OPTIMIZATION_DEMO_GRAPH
    if normalized == "paper":
        return PAPER_DEMO_GRAPH
    raise ValueError(f"unsupported graph demo kind: {kind}")
