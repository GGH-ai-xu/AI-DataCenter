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
