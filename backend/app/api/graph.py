"""图谱导入与知识入图 API。"""

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.auth_access import require_authenticated_user
from app.models.graph_schemas import GraphDraftRequest, GraphExecuteRequest, GraphQaRequest
from app.services.graph_cypher_builder import (
    build_graph_cypher,
    normalize_graph_draft,
    summarize_graph_draft,
)
from app.services.graph_demo_library import get_graph_demo_payload, list_graph_demo_kinds
from app.services.graph_qa import build_graph_answer_context, build_graph_answer_fallback


router = APIRouter(prefix="/api/graph", tags=["Graph"])


async def _graph_summary_payload() -> dict:
    from app.main import app_state

    summary = await app_state.graph.summary()
    summary.update(app_state.local_neo4j.capability(app_state.graph.uri))
    return summary


@router.get("/summary")
async def get_graph_summary():
    return await _graph_summary_payload()


@router.get("/view")
async def get_graph_view(
    request: Request,
    query: str = Query(default="", max_length=120),
    limit: int = Query(default=60, ge=10, le=160),
):
    require_authenticated_user(request)

    from app.main import app_state

    result = await app_state.graph.view_graph(query=query, limit=limit)
    if not result["ok"]:
        status_code = 503 if not result["neo4j_connected"] or not result["configured"] else 500
        raise HTTPException(status_code=status_code, detail=result["message"])
    return result


@router.get("/neighbors")
async def get_graph_neighbors(
    request: Request,
    node_id: str = Query(..., min_length=1, max_length=160),
    limit: int = Query(default=24, ge=1, le=80),
):
    require_authenticated_user(request)

    from app.main import app_state

    result = await app_state.graph.expand_neighbors(node_id=node_id, limit=limit)
    if not result["ok"]:
        if result.get("not_found"):
            raise HTTPException(status_code=404, detail=result["message"])
        status_code = 503 if not result["neo4j_connected"] or not result["configured"] else 500
        raise HTTPException(status_code=status_code, detail=result["message"])
    return result


@router.post("/reconnect")
async def reconnect_graph_service(request: Request):
    require_authenticated_user(request)

    from app.main import app_state

    capability = app_state.local_neo4j.capability(app_state.graph.uri)
    if not capability["local_start_available"]:
        raise HTTPException(status_code=400, detail=capability["local_start_message"])

    await app_state.graph.reset_connection()
    summary = await _graph_summary_payload()
    if summary["ready"]:
        return {
            "success": True,
            "started": False,
            "message": "Neo4j 已在线，已完成连接刷新。",
            "graph_summary": summary,
        }

    start_result = await app_state.local_neo4j.ensure_running(app_state.graph.uri)
    if not start_result["ok"]:
        raise HTTPException(status_code=503, detail=start_result["message"])

    await app_state.graph.reset_connection()
    summary = await _graph_summary_payload()
    if not summary["ready"]:
        raise HTTPException(status_code=503, detail=summary["message"] or "Neo4j 启动后仍未就绪。")

    return {
        "success": True,
        "started": start_result["started"],
        "message": "本地 Neo4j 已启动并连接。" if start_result["started"] else "Neo4j 已完成重连。",
        "graph_summary": summary,
    }


@router.get("/demo/kinds")
async def get_graph_demo_kinds(request: Request):
    require_authenticated_user(request)
    return {
        "kinds": list_graph_demo_kinds(),
        "default_kind": "optimization",
    }


@router.post("/demo/rebuild")
async def rebuild_graph_demo(request: Request, kind: str = Query(default="optimization", pattern=r"^(paper|optimization)$")):
    require_authenticated_user(request)

    from app.main import app_state

    payload = get_graph_demo_payload(kind)
    graph, warnings = normalize_graph_draft(
        payload,
        source=payload.get("source", kind),
        title=payload.get("title", ""),
        mode=payload.get("mode", kind),
        source_type=payload.get("source_type", ""),
        domain_tag=payload.get("domain_tag", ""),
        scenario=payload.get("scenario", ""),
    )
    if not graph["nodes"]:
        raise HTTPException(status_code=400, detail="内置演示图为空，无法重建。")

    clear_result = await app_state.graph.clear_graph()
    if not clear_result["ok"]:
        status_code = 503 if not clear_result["neo4j_connected"] or not clear_result["configured"] else 500
        raise HTTPException(status_code=status_code, detail=clear_result["message"])

    cypher = build_graph_cypher(graph)
    result = await app_state.graph.execute_cypher(cypher)
    if not result["ok"]:
        status_code = 503 if not result["neo4j_connected"] or not result["configured"] else 500
        raise HTTPException(status_code=status_code, detail=result["message"])

    graph_summary = await _graph_summary_payload()
    return {
        "success": True,
        "kind": kind,
        "message": "已切换到优化本体演示图。" if kind == "optimization" else "已切换到论文演示图。",
        "warnings": warnings,
        "draft_summary": summarize_graph_draft(graph),
        "graph_summary": graph_summary,
    }


@router.post("/qa")
async def answer_graph_question(request: Request, req: GraphQaRequest):
    require_authenticated_user(request)

    from app.main import app_state

    graph_view = await app_state.graph.view_graph(query="", limit=120)
    if not graph_view["ok"]:
        status_code = 503 if not graph_view["neo4j_connected"] or not graph_view["configured"] else 500
        raise HTTPException(status_code=status_code, detail=graph_view["message"])

    answer_context = build_graph_answer_context(
        req.question,
        graph_view,
        max_nodes=req.max_nodes,
        max_relationships=req.max_relationships,
    )
    fallback = build_graph_answer_fallback(req.question, answer_context)

    llm_answer = None
    if app_state.llm:
        llm_answer = await app_state.llm.answer_graph_question(
            req.question,
            answer_context["context_text"],
        )

    answer_payload = llm_answer or fallback
    return {
        "question": req.question,
        "summary": answer_payload.get("summary") or fallback["summary"],
        "answer": answer_payload.get("answer") or fallback["answer"],
        "confidence": answer_payload.get("confidence") or fallback["confidence"],
        "evidence": answer_payload.get("evidence") or fallback["evidence"],
        "follow_ups": answer_payload.get("follow_ups") or fallback["follow_ups"],
        "used_llm": bool(llm_answer),
        "matched_node_count": answer_context["matched_node_count"],
        "matched_relationship_count": answer_context["matched_relationship_count"],
        "paper_titles": answer_context["paper_titles"],
        "evidence_nodes": answer_context["evidence_nodes"],
        "evidence_relationships": answer_context["evidence_relationships"],
    }


@router.post("/draft")
async def generate_graph_draft(req: GraphDraftRequest):
    from app.main import app_state

    if not app_state.llm:
        raise HTTPException(status_code=503, detail="LLM 服务未配置，无法生成图谱草稿")

    graph_payload = await app_state.llm.generate_graph_draft(
        req.title,
        req.abstract,
        req.content,
        req.mode,
        req.source,
        req.source_type,
        req.domain_tag,
        req.scenario,
    )
    if not isinstance(graph_payload, dict):
        raise HTTPException(status_code=502, detail="AI 未返回有效的图谱草稿")

    graph, warnings = normalize_graph_draft(
        graph_payload,
        source=req.source,
        title=req.title,
        mode=req.mode,
        source_type=req.source_type,
        domain_tag=req.domain_tag,
        scenario=req.scenario,
    )
    if not graph["nodes"]:
        raise HTTPException(status_code=422, detail="AI 返回了空图谱，请换一段更完整的论文内容再试")

    return {
        "graph": graph,
        "summary": summarize_graph_draft(graph),
        "cypher": build_graph_cypher(graph),
        "warnings": warnings,
    }


@router.post("/execute")
async def execute_graph_import(req: GraphExecuteRequest):
    from app.main import app_state

    graph, warnings = normalize_graph_draft(
        req.graph.model_dump(),
        source=req.source or req.graph.source,
        title=req.graph.title,
        mode=req.graph.mode,
        source_type=req.graph.source_type,
        domain_tag=req.graph.domain_tag,
        scenario=req.graph.scenario,
    )
    if not graph["nodes"]:
        raise HTTPException(status_code=400, detail="当前没有可导入的图谱节点")

    cypher = build_graph_cypher(graph)
    result = await app_state.graph.execute_cypher(cypher)
    if not result["ok"]:
        status_code = 503 if not result["neo4j_connected"] or not result["configured"] else 500
        raise HTTPException(status_code=status_code, detail=result["message"])

    graph_summary = await _graph_summary_payload()
    return {
        **result,
        "warnings": warnings,
        "cypher": cypher,
        "draft_summary": summarize_graph_draft(graph),
        "graph_summary": graph_summary,
    }
