from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_main_registers_graph_router():
    backend_text = (ROOT / "backend" / "app" / "main.py").read_text(
        encoding="utf-8"
    )

    assert "from app.api.graph import router as graph_router" in backend_text
    assert "app.include_router(graph_router)" in backend_text


def test_main_bootstraps_graph_services():
    backend_text = (ROOT / "backend" / "app" / "main.py").read_text(
        encoding="utf-8"
    )

    assert "from app.services.graph_store import GraphStore" in backend_text
    assert "from app.services.local_neo4j import LocalNeo4jService" in backend_text
    assert 'graph_uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")' in backend_text
    assert 'graph_username = os.getenv("NEO4J_USER", "neo4j")' in backend_text
    assert "app_state.graph = GraphStore(" in backend_text
    assert "app_state.local_neo4j = LocalNeo4jService()" in backend_text
