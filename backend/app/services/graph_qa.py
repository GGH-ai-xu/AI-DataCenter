"""图谱问答辅助：从知识图谱里抽取证据并生成可回答上下文。"""

from __future__ import annotations

import re
from typing import Any

from app.services.optimization_ontology import GRAPH_LABEL_PRIORITY

LABEL_PRIORITY = GRAPH_LABEL_PRIORITY

QUESTION_HINTS = {
    "论文": {"Paper"},
    "paper": {"Paper"},
    "方法": {"Method"},
    "method": {"Method"},
    "任务": {"Task"},
    "task": {"Task"},
    "数据集": {"Dataset"},
    "dataset": {"Dataset"},
    "指标": {"Metric"},
    "metric": {"Metric"},
    "策略": {"Policy", "OptimizationStrategy"},
    "policy": {"Policy"},
    "strategy": {"OptimizationStrategy"},
    "约束": {"Constraint"},
    "constraint": {"Constraint"},
    "模板": {"CodeTemplate"},
    "template": {"CodeTemplate"},
    "接口": {"API"},
    "api": {"API"},
    "预算": {"PowerBudget", "CarbonTarget"},
    "高峰期": {"TimePeriod"},
    "低谷期": {"TimePeriod"},
    "任务类型": {"TaskType"},
}

RELATION_HINTS = {
    "提出": {"PROPOSES"},
    "propose": {"PROPOSES"},
    "关系": {"PROPOSES", "SOLVES", "USES", "ACHIEVES"},
    "使用": {"USES"},
    "use": {"USES"},
    "依赖": {"USES"},
    "任务": {"SOLVES"},
    "解决": {"SOLVES"},
    "效果": {"ACHIEVES"},
    "指标": {"ACHIEVES"},
    "约束": {"CONSTRAINS"},
    "限制": {"LIMITS", "CONSTRAINS"},
    "适用": {"APPLIES_TO"},
    "优化": {"OPTIMIZES"},
    "模板": {"USES_TEMPLATE"},
    "接口": {"CALLS_API"},
    "调用": {"CALLS_API"},
    "影响": {"AFFECTS"},
    "触发": {"TRIGGERS"},
    "依赖": {"USES", "REQUIRES"},
}

STOP_WORDS = {
    "the", "and", "with", "from", "that", "this", "what", "which",
    "how", "why", "for", "into", "about", "does", "have", "has",
    "一", "一个", "一下", "哪些", "什么", "怎么", "如何", "请", "帮我",
    "现在", "当前", "这里", "里面", "这个", "这些", "那个", "那些",
    "一下子", "一下吧", "一下呢", "给我", "说明", "介绍", "讲讲",
}

TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-./+]{1,}|[\u4e00-\u9fff]{2,}")


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_lower_text(value: Any) -> str:
    return _normalize_text(value).lower()


def _compare_label_priority(left: str, right: str) -> int:
    diff = LABEL_PRIORITY.get(left, 99) - LABEL_PRIORITY.get(right, 99)
    if diff != 0:
        return diff
    if left < right:
        return -1
    if left > right:
        return 1
    return 0


def _extract_question_tokens(question: str) -> list[str]:
    raw_tokens = []
    for token in TOKEN_RE.findall(_normalize_lower_text(question)):
        normalized = token.strip()
        if len(normalized) < 2 or normalized in STOP_WORDS:
            continue
        raw_tokens.append(normalized)
    seen: set[str] = set()
    ordered: list[str] = []
    for token in raw_tokens:
        if token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return ordered


def _node_haystack(node: dict[str, Any]) -> str:
    parts = [
        node.get("name"),
        node.get("label"),
        node.get("paper_title"),
        node.get("description"),
        node.get("source"),
    ]
    return " ".join(_normalize_lower_text(part) for part in parts if _normalize_text(part))


def _relationship_haystack(relationship: dict[str, Any], node_map: dict[str, dict[str, Any]]) -> str:
    source = node_map.get(relationship.get("source_id", ""), {})
    target = node_map.get(relationship.get("target_id", ""), {})
    parts = [
        relationship.get("type"),
        relationship.get("description"),
        source.get("name"),
        source.get("label"),
        target.get("name"),
        target.get("label"),
    ]
    return " ".join(_normalize_lower_text(part) for part in parts if _normalize_text(part))


def _build_degree_map(relationships: list[dict[str, Any]]) -> dict[str, int]:
    degree_map: dict[str, int] = {}
    for relationship in relationships:
        source_id = _normalize_text(relationship.get("source_id"))
        target_id = _normalize_text(relationship.get("target_id"))
        if source_id:
            degree_map[source_id] = degree_map.get(source_id, 0) + 1
        if target_id:
            degree_map[target_id] = degree_map.get(target_id, 0) + 1
    return degree_map


def _question_labels(question: str) -> set[str]:
    normalized = _normalize_lower_text(question)
    matched: set[str] = set()
    for token, labels in QUESTION_HINTS.items():
        if token in normalized:
            matched.update(labels)
    return matched


def _question_relation_types(question: str) -> set[str]:
    normalized = _normalize_lower_text(question)
    matched: set[str] = set()
    for token, relation_types in RELATION_HINTS.items():
        if token in normalized:
            matched.update(relation_types)
    return matched


def _node_score(
    question: str,
    tokens: list[str],
    hinted_labels: set[str],
    degree_map: dict[str, int],
    node: dict[str, Any],
) -> int:
    haystack = _node_haystack(node)
    normalized_question = _normalize_lower_text(question)
    score = 0
    name = _normalize_lower_text(node.get("name"))
    paper_title = _normalize_lower_text(node.get("paper_title"))
    label = _normalize_text(node.get("label"))

    if name and name in normalized_question:
        score += 36
    if paper_title and paper_title in normalized_question:
        score += 18

    for token in tokens:
        if token and token in haystack:
            score += 8 if len(token) >= 4 else 4

    if hinted_labels and label in hinted_labels:
        score += 10

    score += min(degree_map.get(_normalize_text(node.get("id")), 0), 6)
    return score


def _relationship_score(
    question: str,
    tokens: list[str],
    hinted_types: set[str],
    selected_node_ids: set[str],
    node_map: dict[str, dict[str, Any]],
    relationship: dict[str, Any],
) -> int:
    score = 0
    source_id = _normalize_text(relationship.get("source_id"))
    target_id = _normalize_text(relationship.get("target_id"))
    relation_type = _normalize_text(relationship.get("type"))
    haystack = _relationship_haystack(relationship, node_map)

    if source_id in selected_node_ids and target_id in selected_node_ids:
        score += 20
    elif source_id in selected_node_ids or target_id in selected_node_ids:
        score += 10

    if hinted_types and relation_type in hinted_types:
        score += 8

    normalized_question = _normalize_lower_text(question)
    if relation_type and relation_type.lower() in normalized_question:
        score += 4

    for token in tokens:
        if token and token in haystack:
            score += 4

    return score


def _sort_nodes_for_answer(rows: list[tuple[int, dict[str, Any]]]) -> list[dict[str, Any]]:
    sorted_rows = sorted(
        rows,
        key=lambda item: (
            -item[0],
            LABEL_PRIORITY.get(_normalize_text(item[1].get("label")), 99),
            _normalize_text(item[1].get("name")),
        ),
    )
    return [row[1] for row in sorted_rows]


def _fallback_nodes_by_question(question: str, nodes: list[dict[str, Any]], degree_map: dict[str, int]) -> list[dict[str, Any]]:
    hinted_labels = _question_labels(question)
    if hinted_labels:
        filtered = [node for node in nodes if _normalize_text(node.get("label")) in hinted_labels]
        if filtered:
            return sorted(
                filtered,
                key=lambda node: (
                    -degree_map.get(_normalize_text(node.get("id")), 0),
                    LABEL_PRIORITY.get(_normalize_text(node.get("label")), 99),
                    _normalize_text(node.get("name")),
                ),
            )

    papers = [node for node in nodes if _normalize_text(node.get("label")) == "Paper"]
    if papers:
        return sorted(
            papers,
            key=lambda node: (
                -degree_map.get(_normalize_text(node.get("id")), 0),
                _normalize_text(node.get("paper_title") or node.get("name")),
            ),
        )

    return sorted(
        nodes,
        key=lambda node: (
            -degree_map.get(_normalize_text(node.get("id")), 0),
            LABEL_PRIORITY.get(_normalize_text(node.get("label")), 99),
            _normalize_text(node.get("name")),
        ),
    )


def build_graph_answer_context(
    question: str,
    graph_view: dict[str, Any],
    max_nodes: int = 8,
    max_relationships: int = 10,
) -> dict[str, Any]:
    nodes = list(graph_view.get("nodes") or [])
    relationships = list(graph_view.get("relationships") or [])
    node_map = {_normalize_text(node.get("id")): node for node in nodes}
    degree_map = _build_degree_map(relationships)
    tokens = _extract_question_tokens(question)
    hinted_labels = _question_labels(question)
    hinted_types = _question_relation_types(question)

    ranked_nodes: list[tuple[int, dict[str, Any]]] = []
    for node in nodes:
        score = _node_score(question, tokens, hinted_labels, degree_map, node)
        if score > 0:
            ranked_nodes.append((score, node))

    selected_nodes = _sort_nodes_for_answer(ranked_nodes)[:max_nodes]
    if not selected_nodes:
        selected_nodes = _fallback_nodes_by_question(question, nodes, degree_map)[:max_nodes]

    selected_node_ids = {_normalize_text(node.get("id")) for node in selected_nodes}

    ranked_relationships: list[tuple[int, dict[str, Any]]] = []
    for relationship in relationships:
        score = _relationship_score(
            question,
            tokens,
            hinted_types,
            selected_node_ids,
            node_map,
            relationship,
        )
        if score > 0:
            ranked_relationships.append((score, relationship))

    ranked_relationships.sort(
        key=lambda item: (
            -item[0],
            _normalize_text(item[1].get("type")),
            _normalize_text(item[1].get("source_id")),
            _normalize_text(item[1].get("target_id")),
        ),
    )
    selected_relationships = [item[1] for item in ranked_relationships[:max_relationships]]

    for relationship in selected_relationships:
        for endpoint_id in (
            _normalize_text(relationship.get("source_id")),
            _normalize_text(relationship.get("target_id")),
        ):
            if endpoint_id and endpoint_id not in selected_node_ids and endpoint_id in node_map and len(selected_nodes) < max_nodes:
                selected_nodes.append(node_map[endpoint_id])
                selected_node_ids.add(endpoint_id)

    enriched_relationships = []
    for relationship in selected_relationships:
        source = node_map.get(_normalize_text(relationship.get("source_id")), {})
        target = node_map.get(_normalize_text(relationship.get("target_id")), {})
        enriched_relationships.append({
            **relationship,
            "source_name": _normalize_text(source.get("name") or relationship.get("source_id")),
            "target_name": _normalize_text(target.get("name") or relationship.get("target_id")),
            "source_label": _normalize_text(source.get("label")),
            "target_label": _normalize_text(target.get("label")),
        })

    paper_titles = []
    seen_titles: set[str] = set()
    for node in selected_nodes:
        title = _normalize_text(node.get("paper_title"))
        if title and title not in seen_titles:
            seen_titles.add(title)
            paper_titles.append(title)

    evidence_lines = []
    for node in selected_nodes[:6]:
        node_line = f"[{_normalize_text(node.get('label'))}] {_normalize_text(node.get('name'))}"
        if _normalize_text(node.get("paper_title")):
            node_line += f" | 主题：{_normalize_text(node.get('paper_title'))}"
        if _normalize_text(node.get("description")):
            node_line += f" | 说明：{_normalize_text(node.get('description'))[:120]}"
        evidence_lines.append(node_line)

    for relationship in enriched_relationships[:6]:
        source = node_map.get(_normalize_text(relationship.get("source_id")), {})
        target = node_map.get(_normalize_text(relationship.get("target_id")), {})
        relation_line = (
            f"{_normalize_text(source.get('name') or relationship.get('source_id'))} "
            f"-{_normalize_text(relationship.get('type'))}-> "
            f"{_normalize_text(target.get('name') or relationship.get('target_id'))}"
        )
        if _normalize_text(relationship.get("description")):
            relation_line += f" | {_normalize_text(relationship.get('description'))[:120]}"
        evidence_lines.append(relation_line)

    label_counts = graph_view.get("label_counts") or {}
    relation_type_counts = graph_view.get("relation_type_counts") or {}
    paper_node_count = len([node for node in nodes if _normalize_text(node.get("label")) == "Paper"])
    topic_count = len(paper_titles) if paper_titles else 0
    overview_scope = (
        f"{paper_node_count} 篇论文"
        if paper_node_count
        else (f"{topic_count} 个主题条目" if topic_count else "0 篇论文")
    )
    lines = [
        f"问题：{_normalize_text(question)}",
        (
            f"图库总览：{overview_scope}，"
            f"{len(nodes)} 个节点，{len(relationships)} 条关系。"
        ),
        "可用标签分布：" + "，".join(
            f"{label} {label_counts[label]}"
            for label in sorted(label_counts, key=lambda item: (LABEL_PRIORITY.get(item, 99), item))
        ) if label_counts else "可用标签分布：暂无",
        "可用关系分布：" + "，".join(
            f"{relation_type} {relation_type_counts[relation_type]}"
            for relation_type in sorted(relation_type_counts)
        ) if relation_type_counts else "可用关系分布：暂无",
        "重点证据节点：",
    ]
    lines.extend(f"- {line}" for line in evidence_lines[:6] if line)
    if enriched_relationships:
        lines.append("重点证据关系：")
        for relationship in enriched_relationships[:6]:
            source = node_map.get(_normalize_text(relationship.get("source_id")), {})
            target = node_map.get(_normalize_text(relationship.get("target_id")), {})
            lines.append(
                "- "
                + f"{_normalize_text(source.get('name') or relationship.get('source_id'))} "
                + f"-{_normalize_text(relationship.get('type'))}-> "
                + f"{_normalize_text(target.get('name') or relationship.get('target_id'))}"
                + (
                    f" | {_normalize_text(relationship.get('description'))[:120]}"
                    if _normalize_text(relationship.get("description")) else ""
                )
            )
    lines.append("回答要求：只能依据这些图谱证据回答，信息不足时必须明确说明。")

    follow_ups = []
    for title in paper_titles[:3]:
        follow_ups.append(f"{title} 在图里关联了哪些方法和任务？")
    if selected_relationships:
        source = node_map.get(_normalize_text(selected_relationships[0].get("source_id")), {})
        target = node_map.get(_normalize_text(selected_relationships[0].get("target_id")), {})
        follow_ups.append(
            f"{_normalize_text(source.get('name') or '该节点')} 与 "
            f"{_normalize_text(target.get('name') or '相关节点')} 的关系说明了什么？"
        )
    if not follow_ups:
        if paper_titles:
            follow_ups = [
                "这几篇论文的共同主线是什么？",
                "当前图谱里最核心的方法节点是谁？",
            ]
        else:
            follow_ups = [
                "当前图谱里最核心的优化策略节点是谁？",
                "哪些约束和预算共同决定了当前策略？",
            ]

    return {
        "question": _normalize_text(question),
        "evidence_nodes": selected_nodes,
        "evidence_relationships": enriched_relationships,
        "evidence_lines": evidence_lines,
        "paper_titles": paper_titles,
        "matched_node_count": len(selected_nodes),
        "matched_relationship_count": len(selected_relationships),
        "context_text": "\n".join(line for line in lines if line),
        "follow_ups": follow_ups[:4],
    }


def build_graph_answer_fallback(question: str, context: dict[str, Any]) -> dict[str, Any]:
    evidence_nodes = list(context.get("evidence_nodes") or [])
    evidence_relationships = list(context.get("evidence_relationships") or [])
    matched_node_count = int(context.get("matched_node_count") or 0)
    matched_relationship_count = int(context.get("matched_relationship_count") or 0)

    if not evidence_nodes and not evidence_relationships:
        return {
            "summary": "当前图库里还没有足够证据回答这个问题。",
            "answer": "图谱里没有检索到足够相关的节点或关系。你可以先导入更多图谱内容，或换一个更具体的问题再试。",
            "confidence": "low",
            "evidence": ["当前未检索到可直接支撑回答的图谱证据。"],
            "follow_ups": context.get("follow_ups") or [],
        }

    paper_titles = list(context.get("paper_titles") or [])
    top_node = evidence_nodes[0] if evidence_nodes else None
    summary_parts = []
    if paper_titles:
        summary_parts.append(f"当前回答主要落在 {len(paper_titles)} 个主题条目的图谱证据上")
    if matched_node_count:
        summary_parts.append(f"覆盖 {matched_node_count} 个相关节点")
    if matched_relationship_count:
        summary_parts.append(f"{matched_relationship_count} 条相关关系")
    summary = "，".join(summary_parts) or "已根据当前图谱给出回答"
    if top_node:
        summary += f"，核心节点是“{_normalize_text(top_node.get('name'))}”。"
    else:
        summary += "。"

    answer_lines = [
        f"围绕“{_normalize_text(question)}”，当前图库里检索到了 {matched_node_count} 个相关节点和 {matched_relationship_count} 条相关关系。"
    ]
    if paper_titles:
        answer_lines.append("相关主题包括：" + "、".join(paper_titles[:3]) + "。")
    if evidence_relationships:
        top_relations = []
        node_map = {_normalize_text(node.get("id")): node for node in evidence_nodes}
        for relationship in evidence_relationships[:3]:
            source = node_map.get(_normalize_text(relationship.get("source_id")), {})
            target = node_map.get(_normalize_text(relationship.get("target_id")), {})
            top_relations.append(
                f"{_normalize_text(source.get('name') or relationship.get('source_id'))}"
                f" -{_normalize_text(relationship.get('type'))}-> "
                f"{_normalize_text(target.get('name') or relationship.get('target_id'))}"
            )
        if top_relations:
            answer_lines.append("最直接的图内关系有：" + "；".join(top_relations) + "。")
    if top_node and _normalize_text(top_node.get("description")):
        answer_lines.append("其中最关键的节点说明是：" + _normalize_text(top_node.get("description"))[:160] + "。")

    confidence = "high" if matched_relationship_count >= 2 else "medium"
    if matched_node_count <= 1 and matched_relationship_count == 0:
        confidence = "low"

    return {
        "summary": summary,
        "answer": "".join(answer_lines),
        "confidence": confidence,
        "evidence": list(context.get("evidence_lines") or [])[:6],
        "follow_ups": list(context.get("follow_ups") or [])[:4],
    }
