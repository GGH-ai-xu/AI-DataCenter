import os
import sys
import tempfile
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.connection_settings import ConnectionSettingsService  # noqa: E402


class FakeAgentClient:
    def __init__(self):
        self.base_url = "http://127.0.0.1:8001"
        self.reconfigured = []

    async def reconfigure(self, base_url: str, timeout=None):
        self.base_url = base_url
        self.reconfigured.append(base_url)

    async def health_check(self):
        return {"status": "ok", "gpu_count": 1}


class ConnectionSettingsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.tempdir.name, "connection.json")
        self.service = ConnectionSettingsService(
            self.config_path,
            "http://127.0.0.1:8001",
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_load_creates_default_local_config(self):
        state = self.service.load()

        self.assertEqual(state["mode"], "local")
        self.assertEqual(state["agent_url"], "http://127.0.0.1:8001")
        self.assertTrue(os.path.exists(self.config_path))

    def test_resolve_remote_target_normalizes_url(self):
        mode, url = self.service.resolve_target("remote", "10.0.0.8:9000")

        self.assertEqual(mode, "remote")
        self.assertEqual(url, "http://10.0.0.8:9000")

    def test_resolve_remote_target_adds_default_port(self):
        mode, url = self.service.resolve_target("remote", "10.151.225.108")

        self.assertEqual(mode, "remote")
        self.assertEqual(url, "http://10.151.225.108:8001")

    async def test_update_switches_agent_and_persists(self):
        self.service.load()
        agent = FakeAgentClient()

        result = await self.service.update(
            agent,
            "remote",
            "https://demo.example.com:8443",
            "实验室服务器",
        )

        self.assertEqual(agent.base_url, "https://demo.example.com:8443")
        self.assertEqual(result["mode"], "remote")
        self.assertEqual(result["agent_label"], "实验室服务器")
        self.assertTrue(result["connected"])


if __name__ == "__main__":
    unittest.main()
