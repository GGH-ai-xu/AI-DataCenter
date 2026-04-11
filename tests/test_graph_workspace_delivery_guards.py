import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GraphWorkspaceDeliveryGuardTests(unittest.TestCase):
    def test_backend_public_metadata_uses_new_product_name(self):
        backend_text = (ROOT / "backend" / "app" / "main.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('title="智算中心优化代码生成系统"', backend_text)
        self.assertIn('version="1.1.7"', backend_text)
        self.assertNotIn('title="GPU 共享治理平台"', backend_text)

    def test_backend_runtime_bundles_local_neo4j_scripts(self):
        spec_text = (
            ROOT / "scripts" / "pyinstaller" / "GPUGovernanceBackend.spec"
        ).read_text(encoding="utf-8")

        self.assertIn('ROOT / "scripts" / "start-local-neo4j.ps1"', spec_text)
        self.assertIn('ROOT / "scripts" / "local-neo4j-config.ps1"', spec_text)

    def test_graph_api_uses_extended_timeouts_for_long_running_actions(self):
        api_text = (ROOT / "frontend" / "src" / "services" / "api.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("const GRAPH_LLM_TIMEOUT_MS = 60000", api_text)
        self.assertIn("const GRAPH_RECONNECT_TIMEOUT_MS = 60000", api_text)
        self.assertIn("api.post('/graph/draft', payload, { timeout: GRAPH_LLM_TIMEOUT_MS })", api_text)
        self.assertIn("api.post('/graph/reconnect', null, { timeout: GRAPH_RECONNECT_TIMEOUT_MS })", api_text)
        self.assertIn("api.post('/graph/qa', payload, { timeout: GRAPH_LLM_TIMEOUT_MS })", api_text)
        self.assertIn("api.post('/graph/strategy', payload, { timeout: GRAPH_LLM_TIMEOUT_MS })", api_text)

    def test_graph_workspace_local_timeout_matches_extended_requests(self):
        workspace_text = (
            ROOT / "frontend" / "src" / "composables" / "useGraphWorkspace.js"
        ).read_text(encoding="utf-8")
        view_text = (
            ROOT / "frontend" / "src" / "views" / "AIGraphWorkspace.vue"
        ).read_text(encoding="utf-8")

        self.assertIn("requestTimeoutMs: 65000", workspace_text)
        self.assertIn("function resolveGraphStrategyErrorSummary(error)", view_text)
        self.assertIn("图谱策略生成超时", view_text)

    def test_backend_registers_graph_router_and_bootstraps_graph_services(self):
        backend_text = (ROOT / "backend" / "app" / "main.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("from app.services.graph_store import GraphStore", backend_text)
        self.assertIn("from app.services.local_neo4j import LocalNeo4jService", backend_text)
        self.assertIn('graph_uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")', backend_text)
        self.assertIn('graph_username = os.getenv("NEO4J_USER", "neo4j")', backend_text)
        self.assertIn("app_state.graph = GraphStore(", backend_text)
        self.assertIn("app_state.local_neo4j = LocalNeo4jService()", backend_text)
        self.assertIn("from app.api.graph import router as graph_router", backend_text)
        self.assertIn("app.include_router(graph_router)", backend_text)

    def test_packaged_backend_entry_provides_default_local_neo4j_env(self):
        entry_text = (ROOT / "desktop" / "backend_entry.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('os.environ.setdefault("NEO4J_URI", "bolt://127.0.0.1:7687")', entry_text)
        self.assertIn('os.environ.setdefault("NEO4J_USER", "neo4j")', entry_text)
        self.assertIn('os.environ.setdefault("NEO4J_PASSWORD", "GpuGovNeo4j!2026")', entry_text)
        self.assertIn('os.environ.setdefault("NEO4J_DATABASE", "neo4j")', entry_text)


if __name__ == "__main__":
    unittest.main()
