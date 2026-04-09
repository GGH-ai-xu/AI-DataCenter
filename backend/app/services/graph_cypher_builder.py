"""图谱草稿规范化与 Cypher 构建。"""

from __future__ import annotations

from typing import Any

from app.services.optimization_ontology import (
    get_graph_mode_config,
    graph_source_default,
    graph_source_type_default,
    normalize_graph_mode,
)


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


def _normalize_lookup_key(value: Any) -> str:
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


def _canonical_node_label(value: Any, config: dict[str, Any]) -> str:
    lookup = _normalize_lookup_key(value)
    return config["allowed_node_labels"].get(lookup, "")


def _canonical_relation_type(value: Any, config: dict[str, Any]) -> str:
    lookup = _normalize_lookup_key(value)
    return config["allowed_relation_types"].get(lookup, "")


def _canonical_node_name(label: str, value: Any, config: dict[str, Any]) -> str:
    cleaned = _clean_text(value, 300)
    if not cleaned:
        return ""
    lookup = _normalize_lookup_key(cleaned)
    alias = config.get("node_name_aliases", {}).get(label, {}).get(lookup)
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


def _merge_key_props(node: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    keys = config["node_merge_keys"][node["label"]]
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
        "mode": graph.get("mode", "paper"),
        "source": graph.get("source", ""),
        "source_type": graph.get("source_type", ""),
        "domain_tag": graph.get("domain_tag", ""),
        "scenario": graph.get("scenario", ""),
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
    graph: dict[str, Any],
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
        "mode": graph.get("mode", "paper"),
        "source": graph.get("source", ""),
        "source_type": graph.get("source_type", ""),
        "domain_tag": graph.get("domain_tag", ""),
        "scenario": graph.get("scenario", ""),
        "paper_title": graph.get("title", ""),
    }
    nodes.append(node)
    nodes_by_key[key] = node
    return node


def enrich_graph_draft(graph: dict[str, Any], config: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    nodes = list(graph.get("nodes", []))
    relations = list(graph.get("relations", []))
    nodes_by_key = {_node_key(node): node for node in nodes}
    relation_keys = {(rel["from_id"], rel["type"], rel["to_id"]) for rel in relations}
    supporting_dependencies = config.get("supporting_dependencies", {})
    dependency_source_labels = set(config.get("dependency_source_labels", set()))

    for node in list(nodes):
        if dependency_source_labels and node["label"] not in dependency_source_labels:
            continue
        dependencies = supporting_dependencies.get(node["name"], [])
        for dependency_name in dependencies:
            dependency = _ensure_supporting_node(
                nodes,
                nodes_by_key,
                "Method",
                dependency_name,
                graph,
            )
            rel_key = (node["id"], "USES", dependency["id"])
            if rel_key in relation_keys:
                continue
            relation_keys.add(rel_key)
            relations.append({
                "from_id": node["id"],
                "to_id": dependency["id"],
                "type": "USES",
                "description": f"{node['name']} 建立在 {dependency_name} 之上。",
                "mode": graph.get("mode", "paper"),
                "source": graph.get("source", ""),
                "source_type": graph.get("source_type", ""),
                "domain_tag": graph.get("domain_tag", ""),
                "scenario": graph.get("scenario", ""),
                "paper_title": graph.get("title", ""),
            })

    graph["nodes"] = nodes
    graph["relations"] = relations
    return graph, warnings


def normalize_graph_draft(
    raw: dict[str, Any] | None,
    source: str = "paper",
    title: str = "",
    mode: str = "paper",
    source_type: str = "",
    domain_tag: str = "",
    scenario: str = "",
) -> tuple[dict[str, Any], list[str]]:
    payload = raw or {}
    graph_mode = normalize_graph_mode(payload.get("mode") or mode)
    config = get_graph_mode_config(graph_mode)
    graph_title = _clean_text(payload.get("title") or title, 300)
    graph_source = _clean_text(payload.get("source") or source or graph_source_default(graph_mode), 120) or graph_source_default(graph_mode)
    graph_source_type = _clean_text(
        payload.get("source_type") or source_type or graph_source_type_default(graph_mode),
        120,
    ) or graph_source_type_default(graph_mode)
    graph_domain_tag = _clean_text(payload.get("domain_tag") or domain_tag, 120)
    graph_scenario = _clean_text(payload.get("scenario") or scenario, 200)

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
        label = _canonical_node_label(item.get("label"), config)
        if not label:
            warnings.append(f"第 {index} 个节点类型不在当前模式白名单内，已跳过。")
            continue
        name = _canonical_node_name(label, item.get("name") or item.get("title"), config)
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
            for key, limit in (
                ("description", 2000),
                ("source_type", 120),
                ("domain_tag", 120),
                ("scenario", 200),
            ):
                if not existing.get(key):
                    existing[key] = _clean_text(item.get(key), limit)
            continue

        node = {
            "id": node_id,
            "label": label,
            "name": name,
            "description": _clean_text(item.get("description"), 2000),
            "mode": graph_mode,
            "source": _clean_text(item.get("source") or graph_source, 120),
            "source_type": _clean_text(item.get("source_type") or graph_source_type, 120),
            "domain_tag": _clean_text(item.get("domain_tag") or graph_domain_tag, 120),
            "scenario": _clean_text(item.get("scenario") or graph_scenario, 200),
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
        relation_type = _canonical_relation_type(item.get("type"), config)
        if not relation_type:
            warnings.append(f"第 {index} 条关系类型不在当前模式白名单内，已跳过。")
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
            "mode": graph_mode,
            "source": _clean_text(item.get("source") or graph_source, 120),
            "source_type": _clean_text(item.get("source_type") or graph_source_type, 120),
            "domain_tag": _clean_text(item.get("domain_tag") or graph_domain_tag, 120),
            "scenario": _clean_text(item.get("scenario") or graph_scenario, 200),
            "paper_title": _clean_text(item.get("paper_title") or graph_title, 300),
        })

    graph = {
        "title": graph_title,
        "mode": graph_mode,
        "source": graph_source,
        "source_type": graph_source_type,
        "domain_tag": graph_domain_tag,
        "scenario": graph_scenario,
        "nodes": nodes,
        "relations": relations,
    }
    graph, enrich_warnings = enrich_graph_draft(graph, config)
    warnings.extend(enrich_warnings)
    return graph, warnings


def build_graph_cypher(graph: dict[str, Any]) -> str:
    graph_mode = normalize_graph_mode(graph.get("mode"))
    config = get_graph_mode_config(graph_mode)
    lines = [
        "// Auto-generated knowledge graph import",
        f"// title: {graph.get('title', '')}",
        f"// mode: {graph_mode}",
    ]
    nodes = graph.get("nodes", [])
    relations = graph.get("relations", [])
    node_lookup = {node["id"]: node for node in nodes}

    for index, node in enumerate(nodes):
        var_name = f"n{index}"
        merge_props = _merge_key_props(node, config)
        lines.append(f"MERGE ({var_name}:{node['label']} {_cypher_map(merge_props)})")
        assignments = {
            "mode": node.get("mode", graph_mode),
            "source": node.get("source", ""),
            "source_type": node.get("source_type", ""),
            "domain_tag": node.get("domain_tag", ""),
            "scenario": node.get("scenario", ""),
            "paper_title": node.get("paper_title", ""),
        }
        if node.get("description"):
            assignments["description"] = node["description"]
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
        lines.append(f"MATCH ({from_var}:{from_node['label']} {_cypher_map(_merge_key_props(from_node, config))})")
        lines.append(f"MATCH ({to_var}:{to_node['label']} {_cypher_map(_merge_key_props(to_node, config))})")
        lines.append(f"MERGE ({from_var})-[{rel_var}:{relation['type']}]->({to_var})")
        rel_assignments = {
            "mode": relation.get("mode", graph_mode),
            "source": relation.get("source", ""),
            "source_type": relation.get("source_type", ""),
            "domain_tag": relation.get("domain_tag", ""),
            "scenario": relation.get("scenario", ""),
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
