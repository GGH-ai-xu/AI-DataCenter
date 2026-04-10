import asyncio

from app.services.graph_store import GraphStore, _public_node, _public_relation, _summarize_graph_view


def test_public_node_prefers_primary_label_and_name():
    node = _public_node(
        "node-1",
        ["Task", "Paper"],
        {
            "name": "Self-RAG",
            "description": "paper node",
            "source": "paper",
            "paper_title": "Self-RAG",
        },
    )

    assert node["id"] == "node-1"
    assert node["label"] == "Paper"
    assert node["name"] == "Self-RAG"
    assert node["paper_title"] == "Self-RAG"


def test_public_relation_flattens_edge_payload():
    relation = _public_relation({
        "relation_id": "rel-1",
        "source_id": "a",
        "target_id": "b",
        "type": "PROPOSES",
        "props": {
            "description": "paper proposes method",
            "source": "paper",
            "paper_title": "Self-RAG",
        },
    })

    assert relation["id"] == "rel-1"
    assert relation["source_id"] == "a"
    assert relation["target_id"] == "b"
    assert relation["type"] == "PROPOSES"
    assert relation["paper_title"] == "Self-RAG"


def test_summarize_graph_view_counts_labels_and_relation_types():
    label_counts, relation_counts = _summarize_graph_view(
        [
            {"label": "Paper"},
            {"label": "Method"},
            {"label": "Method"},
        ],
        [
            {"type": "PROPOSES"},
            {"type": "USES"},
            {"type": "USES"},
        ],
    )

    assert label_counts == {"Paper": 1, "Method": 2}
    assert relation_counts == {"PROPOSES": 1, "USES": 2}


class _FakeRecord:
    def __init__(self, payload):
        self._payload = payload

    def __getitem__(self, key):
        return self._payload[key]

    def data(self):
        return dict(self._payload)


class _FakeResult:
    def __init__(self, records):
        self._records = [_FakeRecord(record) for record in records]

    async def single(self):
        return self._records[0] if self._records else None

    def __aiter__(self):
        self._iterator = iter(self._records)
        return self

    async def __anext__(self):
        try:
            return next(self._iterator)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class _FakeSession:
    def __init__(self, responses, calls):
        self._responses = responses
        self._calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def run(self, query, **params):
        self._calls.append((query, params))
        for marker, records in self._responses.items():
            if marker in query:
                return _FakeResult(records)
        raise AssertionError(f"Unexpected query: {query}")


class _FakeDriver:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def session(self, database=None):
        return _FakeSession(self.responses, self.calls)


def test_expand_neighbors_returns_center_neighbors_and_relationships():
    store = GraphStore(uri="bolt://test", username="neo4j", password="password")
    driver = _FakeDriver({
        "MATCH (n)\n                    WHERE elementId(n) = $node_id": [
            {
                "element_id": "method_1",
                "labels": ["Method"],
                "props": {
                    "name": "Self-RAG",
                    "description": "method node",
                    "source": "paper",
                    "paper_title": "Self-RAG",
                },
            },
        ],
        "MATCH (center)-[r]-(neighbor)\n                    WHERE elementId(center) = $node_id\n                    RETURN DISTINCT elementId(neighbor)": [
            {
                "element_id": "paper_1",
                "labels": ["Paper"],
                "props": {
                    "name": "Self-RAG",
                    "description": "paper node",
                    "source": "paper",
                    "paper_title": "Self-RAG",
                },
            },
            {
                "element_id": "task_1",
                "labels": ["Task"],
                "props": {
                    "name": "Open-domain QA",
                    "description": "task node",
                    "source": "paper",
                    "paper_title": "Self-RAG",
                },
            },
        ],
        "MATCH (center)-[r]-(neighbor)\n                    WHERE elementId(center) = $node_id\n                      AND elementId(neighbor) IN $neighbor_ids": [
            {
                "relation_id": "rel_1",
                "source_id": "paper_1",
                "target_id": "method_1",
                "type": "PROPOSES",
                "props": {"description": "paper proposes method"},
            },
            {
                "relation_id": "rel_2",
                "source_id": "method_1",
                "target_id": "task_1",
                "type": "SOLVES",
                "props": {"description": "method solves task"},
            },
        ],
    })

    async def _fake_ensure_driver():
        return driver

    store._ensure_driver = _fake_ensure_driver

    result = asyncio.run(store.expand_neighbors("method_1", limit=8))

    assert result["ok"] is True
    assert result["expanded_node_id"] == "method_1"
    assert result["fetched_neighbor_count"] == 2
    assert [node["id"] for node in result["nodes"]] == ["method_1", "paper_1", "task_1"]
    assert result["label_counts"] == {"Method": 1, "Paper": 1, "Task": 1}
    assert result["relation_type_counts"] == {"PROPOSES": 1, "SOLVES": 1}
    assert result["relationships"][0]["source_id"] == "paper_1"
    assert driver.calls[1][1]["neighbor_limit"] == 8


def test_expand_neighbors_reports_missing_node():
    store = GraphStore(uri="bolt://test", username="neo4j", password="password")
    driver = _FakeDriver({
        "MATCH (n)\n                    WHERE elementId(n) = $node_id": [],
    })

    async def _fake_ensure_driver():
        return driver

    store._ensure_driver = _fake_ensure_driver

    result = asyncio.run(store.expand_neighbors("missing", limit=6))

    assert result["ok"] is False
    assert result["not_found"] is True
    assert result["message"] == "未找到指定的图谱节点。"


def test_view_graph_returns_nodes_and_relationships_for_search():
    store = GraphStore(uri="bolt://test", username="neo4j", password="password")
    driver = _FakeDriver({
        "MATCH (n)\n                    WHERE $search_text = ''": [
            {
                "element_id": "paper_1",
                "labels": ["Paper"],
                "props": {
                    "name": "Self-RAG",
                    "description": "paper node",
                    "source": "paper",
                    "paper_title": "Self-RAG",
                },
            },
            {
                "element_id": "method_1",
                "labels": ["Method"],
                "props": {
                    "name": "Self-RAG",
                    "description": "method node",
                    "source": "paper",
                    "paper_title": "Self-RAG",
                },
            },
        ],
        "MATCH (a)-[r]->(b)\n                    WHERE elementId(a) IN $node_ids": [
            {
                "relation_id": "rel_1",
                "source_id": "paper_1",
                "target_id": "method_1",
                "type": "PROPOSES",
                "props": {"description": "paper proposes method"},
            },
        ],
        "MATCH (a)-[r]-(b)\n                        WHERE elementId(a) IN $node_ids": [],
    })

    async def _fake_ensure_driver():
        return driver

    store._ensure_driver = _fake_ensure_driver

    result = asyncio.run(store.view_graph("self-rag", limit=40))

    assert result["ok"] is True
    assert result["query"] == "self-rag"
    assert result["limit"] == 40
    assert len(result["nodes"]) == 2
    assert len(result["relationships"]) == 1
    assert result["label_counts"] == {"Paper": 1, "Method": 1}
    assert result["relation_type_counts"] == {"PROPOSES": 1}
