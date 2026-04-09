"""重建当前演示用 RAG 论文知识图谱。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.services.graph_cypher_builder import (
    build_graph_cypher,
    normalize_graph_draft,
    summarize_graph_draft,
)
from app.services.graph_store import GraphStore
from app.services.llm_settings import LLMSettingsService


PAPERS = [
    {
        "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        "abstract": (
            "Large pre-trained language models have been shown to store factual knowledge in their parameters, "
            "and achieve state-of-the-art results when fine-tuned on downstream NLP tasks. However, their ability "
            "to access and precisely manipulate knowledge is still limited, and hence on knowledge-intensive tasks, "
            "their performance lags behind task-specific architectures. Additionally, providing provenance for their "
            "decisions and updating their world knowledge remain open research problems. Pre-trained models with a "
            "differentiable access mechanism to explicit non-parametric memory can overcome this issue, but have so "
            "far been only investigated for extractive downstream tasks. We explore a general-purpose fine-tuning "
            "recipe for retrieval-augmented generation (RAG) models which combine pre-trained parametric and "
            "non-parametric memory for language generation. We introduce RAG models where the parametric memory is a "
            "pre-trained seq2seq model and the non-parametric memory is a dense vector index of Wikipedia, accessed "
            "with a pre-trained neural retriever. We compare two RAG formulations, one which conditions on the same "
            "retrieved passages across the whole generated sequence, the other can use different passages per token. "
            "We fine-tune and evaluate our models on a wide range of knowledge-intensive NLP tasks and set the "
            "state-of-the-art on three open domain QA tasks, outperforming parametric seq2seq models and task-specific "
            "retrieve-and-extract architectures. For language generation tasks, we find that RAG models generate more "
            "specific, diverse and factual language than a state-of-the-art parametric-only seq2seq baseline."
        ),
    },
    {
        "title": "Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection",
        "abstract": (
            "Despite their remarkable capabilities, large language models (LLMs) often produce responses containing "
            "factual inaccuracies due to their sole reliance on the parametric knowledge they encapsulate. "
            "Retrieval-Augmented Generation (RAG), an ad hoc approach that augments LMs with retrieval of relevant "
            "knowledge, decreases such issues. However, indiscriminately retrieving and incorporating a fixed number "
            "of retrieved passages, regardless of whether retrieval is necessary, or passages are relevant, diminishes "
            "LM versatility or can lead to unhelpful response generation. We introduce a new framework called "
            "Self-Reflective Retrieval-Augmented Generation (Self-RAG) that enhances an LM's quality and factuality "
            "through retrieval and self-reflection. Our framework trains a single arbitrary LM that adaptively "
            "retrieves passages on-demand, and generates and reflects on retrieved passages and its own generations "
            "using special tokens, called reflection tokens. Generating reflection tokens makes the LM controllable "
            "during the inference phase, enabling it to tailor its behavior to diverse task requirements. Experiments "
            "show that Self-RAG (7B and 13B parameters) significantly outperforms state-of-the-art LLMs and "
            "retrieval-augmented models on a diverse set of tasks. Specifically, Self-RAG outperforms ChatGPT and "
            "retrieval-augmented Llama2-chat on Open-domain QA, reasoning and fact verification tasks, and it shows "
            "significant gains in improving factuality and citation accuracy for long-form generations relative to "
            "these models."
        ),
    },
    {
        "title": "From Local to Global: A Graph RAG Approach to Query-Focused Summarization",
        "abstract": (
            "The use of retrieval-augmented generation (RAG) to retrieve relevant information from an external "
            "knowledge source enables large language models (LLMs) to answer questions over private and/or previously "
            "unseen document collections. However, RAG fails on global questions directed at an entire text corpus, "
            "such as What are the main themes in the dataset?, since this is inherently a query-focused "
            "summarization task rather than an explicit retrieval task. Prior query-focused summarization methods do "
            "not scale to the quantities of text indexed by typical RAG systems. To combine the strengths of these "
            "contrasting methods, we propose GraphRAG, a graph-based approach to question answering over private text "
            "corpora that scales with both the generality of user questions and the quantity of source text. Our "
            "approach uses an LLM to build a graph index in two stages: first, to derive an entity knowledge graph "
            "from the source documents, then to pregenerate community summaries for all groups of closely related "
            "entities. Given a question, each community summary is used to generate a partial response, before all "
            "partial responses are again summarized in a final response to the user. For a class of global "
            "sensemaking questions over datasets in the 1 million token range, we show that GraphRAG leads to "
            "substantial improvements over a conventional RAG baseline for both the comprehensiveness and diversity "
            "of generated answers."
        ),
    },
]


async def rebuild() -> dict:
    repo_root = Path(__file__).resolve().parents[2]
    settings = LLMSettingsService(str(repo_root / "runtime" / "llm.json"))
    settings.load()
    llm = settings.build_service()
    if llm is None:
        raise RuntimeError("LLM service unavailable")

    store = GraphStore(
        uri="bolt://127.0.0.1:7687",
        username="neo4j",
        password="GpuGovNeo4j!2026",
        database="neo4j",
    )
    driver = await store._ensure_driver()
    if driver is None:
        raise RuntimeError("Neo4j unavailable")

    async with driver.session(database="neo4j") as session:
        await session.run("MATCH (n) DETACH DELETE n")

    imported: list[dict] = []
    for paper in PAPERS:
        draft = await llm.generate_graph_draft(paper["title"], paper["abstract"], "", "paper")
        graph, warnings = normalize_graph_draft(draft, source="paper", title=paper["title"])
        result = await store.execute_cypher(build_graph_cypher(graph))
        imported.append({
            "title": paper["title"],
            "summary": summarize_graph_draft(graph),
            "warnings": warnings,
            "result": result,
        })

    final_summary = await store.summary()
    async with driver.session(database="neo4j") as session:
        methods_result = await session.run("MATCH (m:Method) RETURN m.name AS name ORDER BY name")
        methods = [record["name"] async for record in methods_result]
        rel_result = await session.run(
            "MATCH (a)-[r:USES]->(b) RETURN labels(a)[0] AS from_label, a.name AS from_name, labels(b)[0] AS to_label, b.name AS to_name ORDER BY from_name, to_name"
        )
        uses_relations = [record.data() async for record in rel_result]
    await store.close()
    return {
        "imported": imported,
        "final_summary": final_summary,
        "methods": methods,
        "uses_relations": uses_relations,
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(rebuild()), ensure_ascii=False, indent=2))
