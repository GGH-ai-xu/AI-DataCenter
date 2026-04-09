"""图谱草稿规范化与 Cypher 构建。"""

from __future__ import annotations

from typing import Any


ALLOWED_NODE_LABELS = {
    "paper": "Paper",
    "method": "Method",
    "task": "Task",
    "dataset": "Dataset",
    "metric": "Metric",
}

ALLOWED_RELATION_TYPES = {
    "proposes": "PROPOSES",
    "solves": "SOLVES",
    "uses": "USES",
    "achieves": "ACHIEVES",
}

NODE_MERGE_KEYS = {
    "Paper": ("name",),
    "Method": ("name",),
    "Task": ("name",),
    "Dataset": ("name",),
    "Metric": ("name",),
}

NODE_NAME_ALIASES = {
    "Method": {
        "retrieval augmented generation": "Retrieval-Augmented Generation (RAG)",
        "retrieval augmented generation rag": "Retrieval-Augmented Generation (RAG)",
        "retrieval augmented generation rag model": "Retrieval-Augmented Generation (RAG)",
        "rag": "Retrieval-Augmented Generation (RAG)",
        "graph rag": "GraphRAG",
        "self rag": "Self-RAG (Self-Reflective Retrieval-Augmented Generation)",
        "rag sequence": "RAG-Sequence",
        "rag token": "RAG-Token",
    },
    "Task": {
        "open domain qa": "Open-Domain Question Answering (Open-Domain QA)",
        "open domain question answering": "Open-Domain Question Answering (Open-Domain QA)",
        "open domain question answering open domain qa": "Open-Domain Question Answering (Open-Domain QA)",
        "query focused summarization": "Query-Focused Summarization",
        "language generation tasks": "Language Generation",
    },
    "Dataset": {
        "wikipedia corpus": "Wikipedia",
        "wikipedia passages": "Wikipedia",
    },
}

METHOD_DEPENDENCY_MAP = {
    "GraphRAG": ["Retrieval-Augmented Generation (RAG)"],
    "Self-RAG (Self-Reflective Retrieval-Augmented Generation)": ["Retrieval-Augmented Generation (RAG)"],
    "RAG-Sequence": ["Retrieval-Augmented Generation (RAG)"],
    "RAG-Token": ["Retrieval-Augmented Generation (RAG)"],
}


def _clean_text(value: Any, limit: int = 500) -> str:
    text = str(value or "").strip()
    if len(text) > limit:
        return text[:limit].strip()
    return text


def _safe_id(value: Any, fallback: str) -> str:
    raw = _clean_text(value, 120)
    if not raw:
        return fallback
    chars = [ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in raw]
    normalized = "".join(chars).strip("_")
    return normalized or fallback


def _normalize_lookup_key(value: str) -> str:
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


def _cypher_literal(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{text}"'


def _cypher_map(properties: dict[str, Any]) -> str:
    items = [f"{key}: {_cypher_literal(value)}" for key, value in properties.items()]
    return "{ " + ", ".join(items) + " }"


def _canonical_node_label(value: Any) -> str:
    return ALLOWED_NODE_LABELS.get(_clean_text(value, 40).lower(), "")


def _canonical_relation_type(value: Any) -> str:
    return ALLOWED_RELATION_TYPES.get(_clean_text(value, 40).lower(), "")


def _canonical_node_name(label: str, value: Any) -> str:
    cleaned = _clean_text(value, 300)
    if not cleaned:
        return ""
    lookup = _normalize_lookup_key(cleaned)
    alias = NODE_NAME_ALIASES.get(label, {}).get(lookup)
    if alias:
        return alias
    if label == "Method":
        if lookup.startswith("retrieval augmented generation"):
            return "Retrieval-Augmented Generation (RAG)"
        if lookup == "graphrag":
            return "GraphRAG"
        if lookup == "self rag":
            return "Self-RAG (Self-Reflective Retrieval-Augmented Generation)"
    return cleaned


def _merge_key_props(node: dict[str, Any]) -> dict[str, Any]:
    keys = NODE_MERGE_KEYS[node["label"]]
    return {key: node.get(key, "") for key in keys}


def summarize_graph_draft(graph: dict[str, Any]) -> dict[str, Any]:
    label_counts: dict[str, int] = {}
    relation_counts: dict[str, int] = {}
    for node in graph.get("nodes", []):
        label_counts[node["label"]] = label_counts.get(node["label"], 0) + 1
    for relation in graph.get("relations", []):
        relation_counts[relation["type"]] = relation_counts.get(relation["type"], 0) + 1
    return {
        "title": graph.get("title", ""),
        "source": graph.get("source", ""),
        "node_count": len(graph.get("nodes", [])),
        "relation_count": len(graph.get("relations", [])),
        "labels": label_counts,
        "relation_types": relation_counts,
    }


def _node_key(node: dict[str, Any]) -> tuple[str, str]:
    return (node["label"], node["name"].casefold())


def _ensure_supporting_node(
    nodes: list[dict[str, Any]],
    nodes_by_key: dict[tuple[str, str], dict[str, Any]],
    label: str,
    name: str,
    graph_source: str,
) -> dict[str, Any]:
    key = (label, name.casefold())
    existing = nodes_by_key.get(key)
    if existing:
        return existing
    node = {
        "id": _safe_id(f"{label}_{name}", f"{label.lower()}_{len(nodes) + 1}"),
        "label": label,
        "name": name,
        "description": "",
        "source": graph_source,
        "paper_title": "",
    }
    nodes.append(node)
    nodes_by_key[key] = node
    return node


def enrich_graph_draft(graph: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    nodes = list(graph.get("nodes", []))
    relations = list(graph.get("relations", []))
    graph_source = graph.get("source", "paper")
    nodes_by_key = {_node_key(node): node for node in nodes}
    relation_keys = {(rel["from_id"], rel["type"], rel["to_id"]) for rel in relations}

    for node in list(nodes):
        if node["label"] != "Method":
            continue
        dependencies = METHOD_DEPENDENCY_MAP.get(node["name"], [])
        for dependency_name in dependencies:
            dependency = _ensure_supporting_node(
                nodes,
                nodes_by_key,
                "Method",
                dependency_name,
                graph_source,
            )
            rel_key = (node["id"], "USES", dependency["id"])
            if rel_key in relation_keys:
                continue
            relation_keys.add(rel_key)
            relations.append({
                "from_id": node["id"],
                "to_id": dependency["id"],
                "type": "USES",
                "description": f"{node['name']} 建立在 {dependency_name} 的检索增强生成范式之上。",
                "source": graph_source,
                "paper_title": graph.get("title", ""),
            })

    graph["nodes"] = nodes
    graph["relations"] = relations
    return graph, warnings


def normalize_graph_draft(raw: dict[str, Any] | None, source: str = "paper", title: str = "") -> tuple[dict[str, Any], list[str]]:
    payload = raw or {}
    graph_title = _clean_text(payload.get("title") or title, 300)
    graph_source = _clean_text(payload.get("source") or source, 120) or "paper"
    warnings: list[str] = []
    nodes: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    id_map: dict[str, str] = {}
    nodes_by_id: dict[str, dict[str, Any]] = {}
    dedupe_node_key: dict[tuple[str, str], str] = {}

    for index, item in enumerate(payload.get("nodes") or [], start=1):
        if not isinstance(item, dict):
            warnings.append(f"第 {index} 个节点不是对象，已跳过。")
            continue
        label = _canonical_node_label(item.get("label"))
        if not label:
            warnings.append(f"第 {index} 个节点类型不在白名单内，已跳过。")
            continue
        name = _canonical_node_name(label, item.get("name") or item.get("title"))
        if not name:
            warnings.append(f"第 {index} 个节点缺少名称，已跳过。")
            continue
        raw_id = str(item.get("id") or f"node_{index}")
        node_id = _safe_id(raw_id, f"node_{index}")
        paper_title = _clean_text(item.get("paper_title") or graph_title, 300)
        dedupe_key = (label, name.casefold())
        existing_id = dedupe_node_key.get(dedupe_key)
        if existing_id:
            id_map[raw_id] = existing_id
            existing = nodes_by_id[existing_id]
            if not existing.get("description"):
                existing["description"] = _clean_text(item.get("description"), 2000)
            continue

        node = {
            "id": node_id,
            "label": label,
            "name": name,
            "description": _clean_text(item.get("description"), 2000),
            "source": _clean_text(item.get("source") or graph_source, 120),
            "paper_title": paper_title,
        }
        nodes.append(node)
        nodes_by_id[node_id] = node
        dedupe_node_key[dedupe_key] = node_id
        id_map[raw_id] = node_id

    dedupe_relation_key: set[tuple[str, str, str]] = set()
    for index, item in enumerate(payload.get("relations") or [], start=1):
        if not isinstance(item, dict):
            warnings.append(f"第 {index} 条关系不是对象，已跳过。")
            continue
        relation_type = _canonical_relation_type(item.get("type"))
        if not relation_type:
            warnings.append(f"第 {index} 条关系类型不在白名单内，已跳过。")
            continue
        raw_from = str(item.get("from_id") or item.get("from") or "")
        raw_to = str(item.get("to_id") or item.get("to") or "")
        from_id = id_map.get(raw_from)
        to_id = id_map.get(raw_to)
        if not from_id or not to_id:
            warnings.append(f"第 {index} 条关系引用了不存在的节点，已跳过。")
            continue
        rel_key = (from_id, relation_type, to_id)
        if rel_key in dedupe_relation_key:
            continue
        dedupe_relation_key.add(rel_key)
        relations.append({
            "from_id": from_id,
            "to_id": to_id,
            "type": relation_type,
            "description": _clean_text(item.get("description"), 1000),
            "source": _clean_text(item.get("source") or graph_source, 120),
            "paper_title": _clean_text(item.get("paper_title") or graph_title, 300),
        })

    graph = {
        "title": graph_title,
        "source": graph_source,
        "nodes": nodes,
        "relations": relations,
    }
    graph, enrich_warnings = enrich_graph_draft(graph)
    warnings.extend(enrich_warnings)
    return graph, warnings


def build_graph_cypher(graph: dict[str, Any]) -> str:
    lines = [
        "// Auto-generated knowledge graph import",
        f"// title: {graph.get('title', '')}",
    ]
    nodes = graph.get("nodes", [])
    relations = graph.get("relations", [])
    node_lookup = {node["id"]: node for node in nodes}

    for index, node in enumerate(nodes):
        var_name = f"n{index}"
        merge_props = _merge_key_props(node)
        lines.append(f"MERGE ({var_name}:{node['label']} {_cypher_map(merge_props)})")
        assignments = {"source": node.get("source", "")}
        if node["label"] == "Paper" and node.get("paper_title"):
            assignments["paper_title"] = node["paper_title"]
        if node.get("description"):
            assignments["description"] = node["description"]
        if assignments:
            set_clause = ", ".join(
                f"{var_name}.{key} = {_cypher_literal(value)}"
                for key, value in assignments.items()
                if value != ""
            )
            if set_clause:
                lines.append(f"ON CREATE SET {set_clause}")

    if relations and nodes:
        lines.append("WITH 1 AS _")

    for index, relation in enumerate(relations):
        from_node = node_lookup[relation["from_id"]]
        to_node = node_lookup[relation["to_id"]]
        from_var = f"rf{index}"
        to_var = f"rt{index}"
        rel_var = f"rel{index}"
        if index > 0:
            lines.append("WITH 1 AS _")
        lines.append(f"MATCH ({from_var}:{from_node['label']} {_cypher_map(_merge_key_props(from_node))})")
        lines.append(f"MATCH ({to_var}:{to_node['label']} {_cypher_map(_merge_key_props(to_node))})")
        lines.append(f"MERGE ({from_var})-[{rel_var}:{relation['type']}]->({to_var})")
        rel_assignments = {
            "source": relation.get("source", ""),
            "paper_title": relation.get("paper_title", ""),
        }
        if relation.get("description"):
            rel_assignments["description"] = relation["description"]
        set_clause = ", ".join(
            f"{rel_var}.{key} = {_cypher_literal(value)}"
            for key, value in rel_assignments.items()
            if value != ""
        )
        if set_clause:
            lines.append(f"ON CREATE SET {set_clause}")

    lines.append(f"RETURN {len(nodes)} AS nodes_defined, {len(relations)} AS relations_defined")
    return "\n".join(lines)
