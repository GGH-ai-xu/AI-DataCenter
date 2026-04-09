"""Neo4j 图谱存储服务。"""

from __future__ import annotations

import logging
from typing import Any

try:
    from neo4j import AsyncGraphDatabase
except ImportError:  # pragma: no cover - 依赖缺失时走降级路径
    AsyncGraphDatabase = None

from app.services.optimization_ontology import GRAPH_LABEL_PRIORITY


logger = logging.getLogger(__name__)

LABEL_PRIORITY = GRAPH_LABEL_PRIORITY


def _primary_label(labels: list[str]) -> str:
    return min(labels or ["Unknown"], key=lambda value: LABEL_PRIORITY.get(value, 99))


def _public_node(element_id: str, labels: list[str], props: dict[str, Any]) -> dict[str, Any]:
    primary_label = _primary_label(labels)
    return {
        "id": element_id,
        "label": primary_label,
        "labels": labels,
        "name": str(props.get("name") or props.get("paper_title") or element_id),
        "description": str(props.get("description") or ""),
        "mode": str(props.get("mode") or ""),
        "source": str(props.get("source") or ""),
        "source_type": str(props.get("source_type") or ""),
        "domain_tag": str(props.get("domain_tag") or ""),
        "scenario": str(props.get("scenario") or ""),
        "paper_title": str(props.get("paper_title") or ""),
    }


def _public_relation(record: dict[str, Any]) -> dict[str, Any]:
    props = dict(record.get("props") or {})
    return {
        "id": str(record.get("relation_id") or ""),
        "source_id": str(record.get("source_id") or ""),
        "target_id": str(record.get("target_id") or ""),
        "type": str(record.get("type") or ""),
        "description": str(props.get("description") or ""),
        "mode": str(props.get("mode") or ""),
        "source": str(props.get("source") or ""),
        "source_type": str(props.get("source_type") or ""),
        "domain_tag": str(props.get("domain_tag") or ""),
        "scenario": str(props.get("scenario") or ""),
        "paper_title": str(props.get("paper_title") or ""),
    }


def _summarize_graph_view(nodes: list[dict[str, Any]], relationships: list[dict[str, Any]]) -> tuple[dict[str, int], dict[str, int]]:
    label_counts: dict[str, int] = {}
    relation_type_counts: dict[str, int] = {}
    for node in nodes:
        label = str(node.get("label") or "Unknown")
        label_counts[label] = label_counts.get(label, 0) + 1
    for relationship in relationships:
        rel_type = str(relationship.get("type") or "UNKNOWN")
        relation_type_counts[rel_type] = relation_type_counts.get(rel_type, 0) + 1
    return label_counts, relation_type_counts


def _cypher_label_order_case(alias: str) -> str:
    ordered = sorted(LABEL_PRIORITY.items(), key=lambda item: (item[1], item[0]))
    lines = [f"WHEN '{label}' IN labels({alias}) THEN {priority}" for label, priority in ordered]
    lines.append("ELSE 99")
    return "\n                        ".join(lines)


class GraphStore:
    def __init__(self, uri: str = "", username: str = "", password: str = "", database: str = "neo4j"):
        self.uri = (uri or "").strip()
        self.username = (username or "").strip()
        self.password = password or ""
        self.database = (database or "neo4j").strip() or "neo4j"
        self._driver = None
        self._last_error = ""

    @property
    def configured(self) -> bool:
        return bool(self.uri and self.username and self.password)

    @property
    def dependency_installed(self) -> bool:
        return AsyncGraphDatabase is not None

    async def _ensure_driver(self):
        if not self.dependency_installed:
            self._last_error = "未安装 neo4j Python 依赖，请先执行后端依赖安装。"
            return None
        if not self.configured:
            self._last_error = "尚未配置 Neo4j 连接信息。"
            return None
        if self._driver is not None:
            return self._driver

        driver = None
        try:
            driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
            )
            await driver.verify_connectivity()
            self._driver = driver
            self._last_error = ""
            return self._driver
        except Exception as exc:  # pragma: no cover - 依赖真实图数据库环境
            self._last_error = str(exc)
            logger.warning("Neo4j 连接失败: %s", exc)
            if driver is not None:
                try:
                    await driver.close()
                except Exception:
                    pass
            return None

    async def summary(self) -> dict:
        summary = {
            "ready": False,
            "configured": self.configured,
            "dependency_installed": self.dependency_installed,
            "neo4j_connected": False,
            "database": self.database,
            "paper_count": 0,
            "node_count": 0,
            "relation_count": 0,
            "message": self._last_error or "",
        }
        driver = await self._ensure_driver()
        if not driver:
            if not summary["message"]:
                summary["message"] = "Neo4j 当前不可用。"
            return summary

        try:
            async with driver.session(database=self.database) as session:
                paper_result = await session.run("MATCH (p:Paper) RETURN count(p) AS count")
                paper_record = await paper_result.single()
                node_result = await session.run("MATCH (n) RETURN count(n) AS count")
                node_record = await node_result.single()
                rel_result = await session.run("MATCH ()-[r]->() RETURN count(r) AS count")
                rel_record = await rel_result.single()
            summary.update({
                "ready": True,
                "neo4j_connected": True,
                "paper_count": int(paper_record["count"]) if paper_record else 0,
                "node_count": int(node_record["count"]) if node_record else 0,
                "relation_count": int(rel_record["count"]) if rel_record else 0,
                "message": "Neo4j 已就绪",
            })
        except Exception as exc:  # pragma: no cover - 依赖真实图数据库环境
            self._last_error = str(exc)
            logger.warning("读取 Neo4j 摘要失败: %s", exc)
            await self.close()
            summary["message"] = self._last_error
        return summary

    async def execute_cypher(self, cypher: str) -> dict:
        driver = await self._ensure_driver()
        if not driver:
            summary = await self.summary()
            return {
                "ok": False,
                "message": summary["message"] or "Neo4j 当前不可用。",
                "nodes_created": 0,
                "relationships_created": 0,
                "properties_set": 0,
                "neo4j_connected": summary["neo4j_connected"],
                "configured": summary["configured"],
            }

        try:
            async with driver.session(database=self.database) as session:
                result = await session.run(cypher)
                summary = await result.consume()
            counters = summary.counters
            return {
                "ok": True,
                "message": "图谱写入成功",
                "nodes_created": int(counters.nodes_created),
                "relationships_created": int(counters.relationships_created),
                "properties_set": int(counters.properties_set),
                "neo4j_connected": True,
                "configured": True,
            }
        except Exception as exc:  # pragma: no cover - 依赖真实图数据库环境
            self._last_error = str(exc)
            logger.exception("执行 Cypher 失败: %s", exc)
            await self.close()
            return {
                "ok": False,
                "message": self._last_error,
                "nodes_created": 0,
                "relationships_created": 0,
                "properties_set": 0,
                "neo4j_connected": True,
                "configured": True,
            }

    async def clear_graph(self) -> dict:
        return await self.execute_cypher("MATCH (n) DETACH DELETE n")

    async def view_graph(self, query: str = "", limit: int = 60) -> dict:
        driver = await self._ensure_driver()
        if not driver:
            summary = await self.summary()
            return {
                "ok": False,
                "message": summary["message"] or "Neo4j 当前不可用。",
                "nodes": [],
                "relationships": [],
                "label_counts": {},
                "relation_type_counts": {},
                "neo4j_connected": summary["neo4j_connected"],
                "configured": summary["configured"],
                "query": query,
                "limit": limit,
            }

        normalized_query = (query or "").strip().lower()
        safe_limit = max(10, min(int(limit or 60), 160))
        seed_limit = max(5, safe_limit // 2) if normalized_query else safe_limit

        try:
            async with driver.session(database=self.database) as session:
                node_result = await session.run(
                    f"""
                    MATCH (n)
                    WHERE $search_text = ''
                      OR toLower(coalesce(n.name, '')) CONTAINS $search_text
                      OR toLower(coalesce(n.paper_title, '')) CONTAINS $search_text
                      OR toLower(coalesce(n.description, '')) CONTAINS $search_text
                    RETURN elementId(n) AS element_id,
                           labels(n) AS labels,
                           properties(n) AS props
                    ORDER BY
                      CASE
                        {_cypher_label_order_case('n')}
                      END,
                      coalesce(n.name, n.paper_title, elementId(n))
                    LIMIT $seed_limit
                    """,
                    search_text=normalized_query,
                    seed_limit=seed_limit,
                )

                nodes: list[dict[str, Any]] = []
                node_ids: list[str] = []
                node_seen: set[str] = set()
                async for record in node_result:
                    element_id = str(record["element_id"])
                    node_seen.add(element_id)
                    node_ids.append(element_id)
                    nodes.append(_public_node(
                        element_id,
                        list(record["labels"] or []),
                        dict(record["props"] or {}),
                    ))

                if normalized_query and node_ids and len(nodes) < safe_limit:
                    neighbor_result = await session.run(
                        f"""
                        MATCH (a)-[r]-(b)
                        WHERE elementId(a) IN $node_ids
                          AND NOT elementId(b) IN $node_ids
                        RETURN DISTINCT elementId(b) AS element_id,
                               labels(b) AS labels,
                               properties(b) AS props
                        ORDER BY
                          CASE
                            {_cypher_label_order_case('b')}
                          END,
                          coalesce(b.name, b.paper_title, elementId(b))
                        LIMIT $remaining_limit
                        """,
                        node_ids=node_ids,
                        remaining_limit=safe_limit - len(nodes),
                    )
                    async for record in neighbor_result:
                        element_id = str(record["element_id"])
                        if element_id in node_seen:
                            continue
                        node_seen.add(element_id)
                        node_ids.append(element_id)
                        nodes.append(_public_node(
                            element_id,
                            list(record["labels"] or []),
                            dict(record["props"] or {}),
                        ))

                relationship_result = await session.run(
                    """
                    MATCH (a)-[r]->(b)
                    WHERE elementId(a) IN $node_ids
                      AND elementId(b) IN $node_ids
                    RETURN DISTINCT elementId(r) AS relation_id,
                           elementId(a) AS source_id,
                           elementId(b) AS target_id,
                           type(r) AS type,
                           properties(r) AS props
                    ORDER BY type(r), source_id, target_id
                    """,
                    node_ids=node_ids,
                )
                relationships = [_public_relation(record.data()) async for record in relationship_result]

            label_counts, relation_type_counts = _summarize_graph_view(nodes, relationships)
            return {
                "ok": True,
                "message": "图库视图已刷新",
                "query": normalized_query,
                "limit": safe_limit,
                "nodes": nodes,
                "relationships": relationships,
                "label_counts": label_counts,
                "relation_type_counts": relation_type_counts,
                "neo4j_connected": True,
                "configured": True,
            }
        except Exception as exc:  # pragma: no cover - 依赖真实图数据库环境
            self._last_error = str(exc)
            logger.exception("读取图谱视图失败: %s", exc)
            await self.close()
            return {
                "ok": False,
                "message": self._last_error,
                "nodes": [],
                "relationships": [],
                "label_counts": {},
                "relation_type_counts": {},
                "neo4j_connected": True,
                "configured": True,
                "query": normalized_query,
                "limit": safe_limit,
            }

    async def expand_neighbors(self, node_id: str, limit: int = 24) -> dict:
        driver = await self._ensure_driver()
        normalized_node_id = str(node_id or "").strip()
        safe_limit = max(1, min(int(limit or 24), 80))
        if not driver:
            summary = await self.summary()
            return {
                "ok": False,
                "message": summary["message"] or "Neo4j 当前不可用。",
                "expanded_node_id": normalized_node_id,
                "fetched_neighbor_count": 0,
                "nodes": [],
                "relationships": [],
                "label_counts": {},
                "relation_type_counts": {},
                "neo4j_connected": summary["neo4j_connected"],
                "configured": summary["configured"],
                "not_found": False,
            }

        if not normalized_node_id:
            return {
                "ok": False,
                "message": "未提供可展开的图谱节点。",
                "expanded_node_id": normalized_node_id,
                "fetched_neighbor_count": 0,
                "nodes": [],
                "relationships": [],
                "label_counts": {},
                "relation_type_counts": {},
                "neo4j_connected": True,
                "configured": True,
                "not_found": False,
            }

        try:
            async with driver.session(database=self.database) as session:
                center_result = await session.run(
                    """
                    MATCH (n)
                    WHERE elementId(n) = $node_id
                    RETURN elementId(n) AS element_id,
                           labels(n) AS labels,
                           properties(n) AS props
                    """,
                    node_id=normalized_node_id,
                )
                center_record = await center_result.single()
                if not center_record:
                    return {
                        "ok": False,
                        "message": "未找到指定的图谱节点。",
                        "expanded_node_id": normalized_node_id,
                        "fetched_neighbor_count": 0,
                        "nodes": [],
                        "relationships": [],
                        "label_counts": {},
                        "relation_type_counts": {},
                        "neo4j_connected": True,
                        "configured": True,
                        "not_found": True,
                    }

                nodes = [_public_node(
                    str(center_record["element_id"]),
                    list(center_record["labels"] or []),
                    dict(center_record["props"] or {}),
                )]
                node_ids = [normalized_node_id]
                node_seen = {normalized_node_id}

                neighbor_result = await session.run(
                    f"""
                    MATCH (center)-[r]-(neighbor)
                    WHERE elementId(center) = $node_id
                    RETURN DISTINCT elementId(neighbor) AS element_id,
                           labels(neighbor) AS labels,
                           properties(neighbor) AS props
                    ORDER BY
                      CASE
                        {_cypher_label_order_case('neighbor')}
                      END,
                      coalesce(neighbor.name, neighbor.paper_title, elementId(neighbor))
                    LIMIT $neighbor_limit
                    """,
                    node_id=normalized_node_id,
                    neighbor_limit=safe_limit,
                )
                async for record in neighbor_result:
                    element_id = str(record["element_id"])
                    if element_id in node_seen:
                        continue
                    node_seen.add(element_id)
                    node_ids.append(element_id)
                    nodes.append(_public_node(
                        element_id,
                        list(record["labels"] or []),
                        dict(record["props"] or {}),
                    ))

                relationship_result = await session.run(
                    """
                    MATCH (center)-[r]-(neighbor)
                    WHERE elementId(center) = $node_id
                      AND elementId(neighbor) IN $neighbor_ids
                    RETURN DISTINCT elementId(r) AS relation_id,
                           elementId(startNode(r)) AS source_id,
                           elementId(endNode(r)) AS target_id,
                           type(r) AS type,
                           properties(r) AS props
                    ORDER BY type(r), source_id, target_id
                    """,
                    node_id=normalized_node_id,
                    neighbor_ids=node_ids,
                )
                relationships = [_public_relation(record.data()) async for record in relationship_result]

            label_counts, relation_type_counts = _summarize_graph_view(nodes, relationships)
            return {
                "ok": True,
                "message": "节点邻居已展开",
                "expanded_node_id": normalized_node_id,
                "fetched_neighbor_count": max(0, len(nodes) - 1),
                "nodes": nodes,
                "relationships": relationships,
                "label_counts": label_counts,
                "relation_type_counts": relation_type_counts,
                "neo4j_connected": True,
                "configured": True,
                "not_found": False,
            }
        except Exception as exc:  # pragma: no cover - 依赖真实图数据库环境
            self._last_error = str(exc)
            logger.exception("展开图谱节点邻居失败: %s", exc)
            await self.close()
            return {
                "ok": False,
                "message": self._last_error,
                "expanded_node_id": normalized_node_id,
                "fetched_neighbor_count": 0,
                "nodes": [],
                "relationships": [],
                "label_counts": {},
                "relation_type_counts": {},
                "neo4j_connected": True,
                "configured": True,
                "not_found": False,
            }

    async def reset_connection(self) -> None:
        self._last_error = ""
        await self.close()

    async def close(self) -> None:
        if self._driver is None:
            return
        await self._driver.close()
        self._driver = None
