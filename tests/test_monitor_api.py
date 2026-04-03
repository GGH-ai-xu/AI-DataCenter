import os
import sys
import types
import unittest
from unittest import mock


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.api.monitor import get_system_detail, get_training_progress  # noqa: E402
from app.services.http_agent_provider import HttpAgentProvider  # noqa: E402
from app.services.runtime_provider import RuntimeTarget  # noqa: E402


class MonitorApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_system_detail_route_supports_http_runtime_provider(self):
        provider = HttpAgentProvider(
            RuntimeTarget(
                provider_type="http_remote",
                label="实验室 A",
                agent_url="http://127.0.0.1:8001",
            )
        )
        provider.client = types.SimpleNamespace(
            get_system_detail=mock.AsyncMock(
                return_value={
                    "cpu_percent": 31.5,
                    "cpu_per_core": [28.0, 35.0],
                    "network": {"bytes_sent": 10, "bytes_recv": 20},
                }
            ),
            get_system_info=mock.AsyncMock(return_value={"cpu_percent": 20.0}),
            close=mock.AsyncMock(),
        )
        fake_main = types.SimpleNamespace(
            app_state=types.SimpleNamespace(agent=provider)
        )

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            payload = await get_system_detail()

        self.assertEqual(payload["cpu_percent"], 31.5)
        self.assertEqual(payload["cpu_per_core"], [28.0, 35.0])
        self.assertEqual(payload["network"]["bytes_recv"], 20)

    async def test_training_route_filters_logs_to_imported_gpus(self):
        provider = HttpAgentProvider(
            RuntimeTarget(
                provider_type="http_remote",
                label="实验室 A",
                agent_url="http://127.0.0.1:8001",
            )
        )
        provider.client = types.SimpleNamespace(
            get_training_logs=mock.AsyncMock(
                return_value=[
                    {"pid": 10, "gpu_index": 0, "username": "alice"},
                    {"pid": 11, "gpu_index": 1, "username": "bob"},
                ]
            ),
            close=mock.AsyncMock(),
        )
        fake_main = types.SimpleNamespace(
            app_state=types.SimpleNamespace(
                agent=provider,
                import_context=types.SimpleNamespace(
                    selected_gpu_indexes=lambda: [1],
                ),
                privacy=types.SimpleNamespace(
                    sanitize_training_logs=lambda logs: logs,
                ),
            )
        )

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            payload = await get_training_progress()

        self.assertEqual([item["pid"] for item in payload["training"]], [11])


if __name__ == "__main__":
    unittest.main()
