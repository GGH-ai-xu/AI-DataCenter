import json

from app.services.graph_strategy import (
    build_graph_strategy_context,
    build_graph_strategy_fallback,
)


def _mixed_graph_view():
    return {
        "nodes": [
            {
                "id": "paper_1",
                "label": "Paper",
                "name": "Self-RAG",
                "paper_title": "Self-RAG",
                "description": "paper node",
                "source": "paper",
            },
            {
                "id": "strategy_1",
                "label": "OptimizationStrategy",
                "name": "高峰限功调度",
                "paper_title": "绿算生金优化本体",
                "description": "高峰期优先降低低负载 GPU 功率。",
                "source": "optimization",
            },
            {
                "id": "constraint_1",
                "label": "Constraint",
                "name": "紧急任务不可暂停",
                "paper_title": "绿算生金优化本体",
                "description": "urgent 任务不能被暂停。",
                "source": "optimization",
            },
            {
                "id": "metric_1",
                "label": "Metric",
                "name": "总功耗",
                "paper_title": "绿算生金优化本体",
                "description": "核心能耗指标。",
                "source": "optimization",
            },
            {
                "id": "template_1",
                "label": "CodeTemplate",
                "name": "scheduler_power_guard",
                "paper_title": "绿算生金优化本体",
                "description": "保护紧急任务前提下执行限功策略的模板。",
                "source": "optimization",
            },
            {
                "id": "api_1",
                "label": "API",
                "name": "set_power_limit",
                "paper_title": "绿算生金优化本体",
                "description": "限功接口。",
                "source": "optimization",
            },
            {
                "id": "api_2",
                "label": "API",
                "name": "run_schedule_once",
                "paper_title": "绿算生金优化本体",
                "description": "调度接口。",
                "source": "optimization",
            },
        ],
        "relationships": [
            {
                "id": "rel_1",
                "source_id": "strategy_1",
                "target_id": "constraint_1",
                "type": "REQUIRES",
                "description": "策略必须满足紧急任务保护。",
                "paper_title": "绿算生金优化本体",
            },
            {
                "id": "rel_2",
                "source_id": "strategy_1",
                "target_id": "metric_1",
                "type": "OPTIMIZES",
                "description": "策略目标是降低总功耗。",
                "paper_title": "绿算生金优化本体",
            },
            {
                "id": "rel_3",
                "source_id": "strategy_1",
                "target_id": "template_1",
                "type": "USES_TEMPLATE",
                "description": "策略依赖模板。",
                "paper_title": "绿算生金优化本体",
            },
            {
                "id": "rel_4",
                "source_id": "template_1",
                "target_id": "api_1",
                "type": "CALLS_API",
                "description": "模板会调用限功接口。",
                "paper_title": "绿算生金优化本体",
            },
            {
                "id": "rel_5",
                "source_id": "template_1",
                "target_id": "api_2",
                "type": "CALLS_API",
                "description": "模板会调用调度接口。",
                "paper_title": "绿算生金优化本体",
            },
        ],
        "label_counts": {
            "Paper": 1,
            "OptimizationStrategy": 1,
            "Constraint": 1,
            "Metric": 1,
            "CodeTemplate": 1,
            "API": 2,
        },
        "relation_type_counts": {
            "REQUIRES": 1,
            "OPTIMIZES": 1,
            "USES_TEMPLATE": 1,
            "CALLS_API": 2,
        },
    }


def _control_context():
    return {
        "llm_context": json.dumps({
            "time_period": "高峰期",
            "budget": {
                "enabled": True,
                "total_power_budget": 1200,
            },
            "gpus": [
                {
                    "index": 0,
                    "power_usage": 280.0,
                    "gpu_utilization": 25,
                    "temperature": 72,
                },
                {
                    "index": 1,
                    "power_usage": 300.0,
                    "gpu_utilization": 84,
                    "temperature": 79,
                },
            ],
            "manageable_processes": [
                {"pid": 1234, "priority": "urgent"},
                {"pid": 5678, "priority": "deferrable"},
            ],
        }, ensure_ascii=False),
    }


def test_build_graph_strategy_context_prefers_optimization_nodes():
    context = build_graph_strategy_context(
        "高峰期降低总功耗，但不影响紧急任务",
        _mixed_graph_view(),
        _control_context(),
        max_nodes=8,
        max_relationships=8,
    )

    node_labels = {node["label"] for node in context["evidence_nodes"]}

    assert "Paper" not in node_labels
    assert "OptimizationStrategy" in node_labels
    assert "Constraint" in node_labels
    assert context["focus"]["strategies"] == ["高峰限功调度"]
    assert "高峰期" in context["runtime_summary"]


def test_build_graph_strategy_fallback_returns_code_and_control_prompt():
    context = build_graph_strategy_context(
        "高峰期降低总功耗，但不影响紧急任务",
        _mixed_graph_view(),
        _control_context(),
        max_nodes=8,
        max_relationships=8,
    )
    fallback = build_graph_strategy_fallback(
        "高峰期降低总功耗，但不影响紧急任务",
        context,
    )

    assert "高峰限功调度" in fallback["summary"]
    assert len(fallback["strategy_steps"]) >= 4
    assert "set_power_limit" in fallback["code_snippet"]
    assert "run_schedule_once" in fallback["code_snippet"]
    assert "保守优化" in fallback["control_prompt"]
    assert fallback["evidence"]
