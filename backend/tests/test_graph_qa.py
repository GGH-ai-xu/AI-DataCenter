from app.services.graph_qa import build_graph_answer_context, build_graph_answer_fallback


def _demo_graph_view():
    return {
        "nodes": [
            {
                "id": "paper_1",
                "label": "Paper",
                "name": "Self-RAG",
                "paper_title": "Self-RAG",
                "description": "A self-reflective retrieval-augmented generation paper.",
                "source": "paper",
            },
            {
                "id": "method_1",
                "label": "Method",
                "name": "Self-RAG (Self-Reflective Retrieval-Augmented Generation)",
                "paper_title": "Self-RAG",
                "description": "Self-reflective RAG pipeline.",
                "source": "paper",
            },
            {
                "id": "method_2",
                "label": "Method",
                "name": "Retrieval-Augmented Generation (RAG)",
                "paper_title": "RAG",
                "description": "Base retrieval-augmented generation paradigm.",
                "source": "paper",
            },
            {
                "id": "task_1",
                "label": "Task",
                "name": "Open-Domain Question Answering (Open-Domain QA)",
                "paper_title": "Self-RAG",
                "description": "Open-domain QA task.",
                "source": "paper",
            },
        ],
        "relationships": [
            {
                "id": "rel_1",
                "source_id": "paper_1",
                "target_id": "method_1",
                "type": "PROPOSES",
                "description": "Self-RAG paper proposes the Self-RAG method.",
                "paper_title": "Self-RAG",
            },
            {
                "id": "rel_2",
                "source_id": "method_1",
                "target_id": "method_2",
                "type": "USES",
                "description": "Self-RAG builds on the base RAG paradigm.",
                "paper_title": "Self-RAG",
            },
            {
                "id": "rel_3",
                "source_id": "method_1",
                "target_id": "task_1",
                "type": "SOLVES",
                "description": "Self-RAG is evaluated on open-domain QA.",
                "paper_title": "Self-RAG",
            },
        ],
        "label_counts": {
            "Paper": 1,
            "Method": 2,
            "Task": 1,
        },
        "relation_type_counts": {
            "PROPOSES": 1,
            "USES": 1,
            "SOLVES": 1,
        },
    }


def test_build_graph_answer_context_selects_relevant_nodes_and_relationships():
    context = build_graph_answer_context(
        "Self-RAG 和 RAG 有什么关系？",
        _demo_graph_view(),
        max_nodes=6,
        max_relationships=6,
    )

    node_names = {node["name"] for node in context["evidence_nodes"]}
    relation_types = {relationship["type"] for relationship in context["evidence_relationships"]}

    assert "Self-RAG (Self-Reflective Retrieval-Augmented Generation)" in node_names
    assert "Retrieval-Augmented Generation (RAG)" in node_names
    assert "USES" in relation_types
    assert context["matched_node_count"] >= 2
    assert context["matched_relationship_count"] >= 1
    assert "回答要求：只能依据这些图谱证据回答" in context["context_text"]


def test_build_graph_answer_fallback_reports_evidence_and_followups():
    context = build_graph_answer_context(
        "这篇论文解决了什么任务？",
        _demo_graph_view(),
        max_nodes=6,
        max_relationships=6,
    )
    fallback = build_graph_answer_fallback("这篇论文解决了什么任务？", context)

    assert "Open-Domain Question Answering" in fallback["answer"]
    assert fallback["confidence"] in {"medium", "high"}
    assert fallback["evidence"]
    assert fallback["follow_ups"]
