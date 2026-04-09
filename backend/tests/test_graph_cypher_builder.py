from app.services.graph_cypher_builder import (
    build_graph_cypher,
    normalize_graph_draft,
    summarize_graph_draft,
)


def test_normalize_graph_draft_keeps_whitelisted_nodes_and_relations():
    graph, warnings = normalize_graph_draft(
        {
            "title": "GraphRAG",
            "nodes": [
                {"id": "paper_1", "label": "Paper", "name": "GraphRAG"},
                {"id": "method_1", "label": "Method", "name": "GraphRAG Method"},
                {"id": "bad_1", "label": "Person", "name": "Someone"},
                {"id": "method_1_dup", "label": "method", "name": "GraphRAG Method"},
            ],
            "relations": [
                {"from_id": "paper_1", "to_id": "method_1", "type": "PROPOSES"},
                {"from_id": "paper_1", "to_id": "bad_1", "type": "USES"},
            ],
        },
        source="paper",
        title="GraphRAG",
    )

    assert len(graph["nodes"]) == 2
    assert len(graph["relations"]) == 1
    assert graph["nodes"][1]["label"] == "Method"
    assert graph["relations"][0]["type"] == "PROPOSES"
    assert warnings


def test_normalize_graph_draft_canonicalizes_and_enriches_rag_family():
    graph, warnings = normalize_graph_draft(
        {
            "title": "Self-RAG",
            "nodes": [
                {"id": "paper_1", "label": "Paper", "name": "Self-RAG"},
                {"id": "method_1", "label": "Method", "name": "Self-RAG"},
                {"id": "task_1", "label": "Task", "name": "Open-domain QA"},
            ],
            "relations": [
                {"from_id": "paper_1", "to_id": "method_1", "type": "PROPOSES"},
                {"from_id": "method_1", "to_id": "task_1", "type": "SOLVES"},
            ],
        },
        source="paper",
        title="Self-RAG",
    )

    method_names = {node["name"] for node in graph["nodes"] if node["label"] == "Method"}
    task_names = {node["name"] for node in graph["nodes"] if node["label"] == "Task"}
    uses_pairs = {
        (rel["from_id"], rel["type"], rel["to_id"])
        for rel in graph["relations"]
        if rel["type"] == "USES"
    }
    node_by_name = {node["name"]: node["id"] for node in graph["nodes"]}

    assert "Self-RAG (Self-Reflective Retrieval-Augmented Generation)" in method_names
    assert "Retrieval-Augmented Generation (RAG)" in method_names
    assert "Open-Domain Question Answering (Open-Domain QA)" in task_names
    assert (
        node_by_name["Self-RAG (Self-Reflective Retrieval-Augmented Generation)"],
        "USES",
        node_by_name["Retrieval-Augmented Generation (RAG)"],
    ) in uses_pairs
    assert warnings == []


def test_build_graph_cypher_produces_merge_only_preview():
    graph = {
        "title": "GraphRAG",
        "source": "paper",
        "nodes": [
            {
                "id": "paper_1",
                "label": "Paper",
                "name": "GraphRAG",
                "description": "A graph retrieval paper",
                "source": "paper",
                "paper_title": "GraphRAG",
            },
            {
                "id": "method_1",
                "label": "Method",
                "name": "GraphRAG Method",
                "description": "",
                "source": "paper",
                "paper_title": "GraphRAG",
            },
        ],
        "relations": [
            {
                "from_id": "paper_1",
                "to_id": "method_1",
                "type": "PROPOSES",
                "description": "paper proposes method",
                "source": "paper",
                "paper_title": "GraphRAG",
            },
        ],
    }

    cypher = build_graph_cypher(graph)
    summary = summarize_graph_draft(graph)

    assert "MERGE (n0:Paper" in cypher
    assert "MERGE (rf0)-[rel0:PROPOSES]->(rt0)" in cypher
    assert "DETACH DELETE" not in cypher
    assert summary["node_count"] == 2
    assert summary["relation_count"] == 1


def test_normalize_graph_draft_supports_optimization_mode():
    graph, warnings = normalize_graph_draft(
        {
            "title": "智算中心优化规则",
            "mode": "optimization",
            "source": "optimization",
            "source_type": "rule",
            "domain_tag": "智算中心优化",
            "scenario": "高峰限功",
            "nodes": [
                {"id": "policy_1", "label": "策略", "name": "三层调度总则"},
                {"id": "constraint_1", "label": "约束", "name": "紧急任务不可暂停"},
                {"id": "strategy_1", "label": "strategy", "name": "高峰限功调度"},
                {"id": "template_1", "label": "代码模板", "name": "scheduler_power_guard"},
            ],
            "relations": [
                {"from_id": "policy_1", "to_id": "constraint_1", "type": "约束"},
                {"from_id": "strategy_1", "to_id": "template_1", "type": "uses template"},
            ],
        },
        source="optimization",
        title="智算中心优化规则",
        mode="optimization",
        source_type="rule",
        domain_tag="智算中心优化",
        scenario="高峰限功",
    )

    labels = {node["label"] for node in graph["nodes"]}
    relation_types = {relation["type"] for relation in graph["relations"]}

    assert labels == {"Policy", "Constraint", "OptimizationStrategy", "CodeTemplate"}
    assert relation_types == {"CONSTRAINS", "USES_TEMPLATE"}
    assert graph["mode"] == "optimization"
    assert graph["source_type"] == "rule"
    assert graph["domain_tag"] == "智算中心优化"
    assert graph["scenario"] == "高峰限功"
    assert warnings == []


def test_build_graph_cypher_includes_optimization_metadata():
    graph = {
        "title": "绿算生金优化本体",
        "mode": "optimization",
        "source": "optimization",
        "source_type": "strategy",
        "domain_tag": "智算中心优化",
        "scenario": "预算触发",
        "nodes": [
            {
                "id": "strategy_1",
                "label": "OptimizationStrategy",
                "name": "预算触发调度",
                "description": "当预算触顶时触发调度。",
                "mode": "optimization",
                "source": "optimization",
                "source_type": "strategy",
                "domain_tag": "智算中心优化",
                "scenario": "预算触发",
                "paper_title": "绿算生金优化本体",
            },
            {
                "id": "metric_1",
                "label": "Metric",
                "name": "总功耗",
                "description": "",
                "mode": "optimization",
                "source": "optimization",
                "source_type": "strategy",
                "domain_tag": "智算中心优化",
                "scenario": "预算触发",
                "paper_title": "绿算生金优化本体",
            },
        ],
        "relations": [
            {
                "from_id": "strategy_1",
                "to_id": "metric_1",
                "type": "OPTIMIZES",
                "description": "目标是压低总功耗。",
                "mode": "optimization",
                "source": "optimization",
                "source_type": "strategy",
                "domain_tag": "智算中心优化",
                "scenario": "预算触发",
                "paper_title": "绿算生金优化本体",
            },
        ],
    }

    cypher = build_graph_cypher(graph)

    assert "// mode: optimization" in cypher
    assert "MERGE (n0:OptimizationStrategy" in cypher
    assert "source_type = \"strategy\"" in cypher
    assert "domain_tag = \"智算中心优化\"" in cypher
    assert "MERGE (rf0)-[rel0:OPTIMIZES]->(rt0)" in cypher
