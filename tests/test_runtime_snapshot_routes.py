import os
import sys
import types
import unittest
from unittest import mock


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.api.governance import get_fairness_governance  # noqa: E402
from app.api.scheduler import get_scheduler_status  # noqa: E402
from app.api.system_diagnostics import self_check  # noqa: E402
from app.services.runtime_overview import build_health_payload  # noqa: E402


def _build_snapshot() -> dict:
    return {
        "collected_at": 1710000000.0,
        "agent_health": {"status": "ok"},
        "runtime": {"status": "connected", "connected": True},
        "import_context": {
            "valid": True,
            "imported_gpu_indexes": [1],
            "invalid_reason": "",
        },
        "raw": {
            "system": {"cpu_percent": 12},
            "gpus": [
                {"index": 0, "name": "BROKEN"},
                {"index": 1, "name": "GPU1"},
            ],
            "processes": [
                {"pid": 10, "gpu_index": 0},
                {"pid": 11, "gpu_index": 1},
            ],
        },
        "scoped": {
            "system": {"cpu_percent": 12},
            "gpus": [{"index": 1, "name": "GPU1"}],
            "processes": [{"pid": 11, "gpu_index": 1}],
            "public_processes": [{"pid": 11, "gpu_index": 1}],
        },
    }


class ExplodingAgent:
    async def health_check(self):
        raise AssertionError("health_check should not run when snapshot is available")

    async def get_all_gpus(self):
        raise AssertionError("get_all_gpus should not run when snapshot is available")

    async def get_system_info(self):
        raise AssertionError("get_system_info should not run when snapshot is available")

    async def get_processes(self):
        raise AssertionError("get_processes should not run when snapshot is available")


class FakeRuntime:
    def __init__(self, status: dict):
        self._status = status

    async def status(self):
        return dict(self._status)


class FakeConnection:
    def snapshot(self, health):
        return {
            "connected": health is not None,
            "mode_label": "SSH Linux",
            "agent_url": "ssh://demo",
        }


class FakeScheduler:
    def __init__(self):
        self.auto_enabled = True
        self.budget_gpus = None

    def get_budget_status(self, gpus):
        self.budget_gpus = list(gpus or [])
        return {
            "enabled": True,
            "current_total_power": 320.0,
            "total_power_budget": 900.0,
        }

    def get_carbon_budget_status(self, gpus):
        return {"gpu_count": len(gpus or [])}


class FakeGovernance:
    def __init__(self):
        self.calls = []

    async def get_fairness_report(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "overview": {"fairness_index": 95},
            "users": [],
            "yield_candidates": [],
            "recommendations": [],
        }


class FakePrivacy:
    def sanitize_governance_report(self, report):
        return report


class FakeImportContext:
    def selected_gpu_indexes(self):
        return [1]


class FakeLlmSettings:
    def snapshot(self, available):
        return {"enabled": available}


class RuntimeSnapshotRouteTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.snapshot = _build_snapshot()
        self.runtime = FakeRuntime({"status": "connected", "connected": True})
        self.connection = FakeConnection()
        self.scheduler = FakeScheduler()
        self.governance = FakeGovernance()
        self.app_state = types.SimpleNamespace(
            agent=ExplodingAgent(),
            latest_runtime_snapshot=self.snapshot,
            runtime=self.runtime,
            connection=self.connection,
            scheduler=self.scheduler,
            governance=self.governance,
            privacy=FakePrivacy(),
            import_context=FakeImportContext(),
            llm=object(),
            llm_settings=FakeLlmSettings(),
        )
        self.fake_main = types.SimpleNamespace(
            app_state=self.app_state,
            runtime_status_payload=self.runtime.status,
        )
        self.main_patch = mock.patch.dict(sys.modules, {"app.main": self.fake_main})
        self.main_patch.start()

    def tearDown(self):
        self.main_patch.stop()

    async def test_health_uses_cached_snapshot_without_agent_calls(self):
        payload = await build_health_payload(
            runtime_status=await self.runtime.status(),
            snapshot=self.snapshot,
            connection_factory=self.connection.snapshot,
            llm_available=True,
            llm_snapshot=self.app_state.llm_settings.snapshot(True),
            ws_connections=0,
            fallback_loader=mock.AsyncMock(
                side_effect=AssertionError("fallback_loader should not run when snapshot is available")
            ),
        )

        self.assertEqual(payload["data_source"], "cache")
        self.assertTrue(payload["agent_connected"])
        self.assertTrue(payload["workspace_ready"])
        self.assertEqual(payload["import_context"]["imported_gpu_indexes"], [1])

    async def test_scheduler_status_uses_cached_scoped_gpus(self):
        payload = await get_scheduler_status()

        self.assertEqual([gpu["index"] for gpu in self.scheduler.budget_gpus], [1])
        self.assertEqual(payload["carbon"]["gpu_count"], 1)

    async def test_fairness_uses_cached_scoped_snapshot(self):
        payload = await get_fairness_governance()

        self.assertEqual(payload["overview"]["fairness_index"], 95)
        self.assertEqual(len(self.governance.calls), 1)
        self.assertEqual(self.governance.calls[0]["gpu_indexes"], [1])
        self.assertEqual(self.governance.calls[0]["gpus"], [{"index": 1, "name": "GPU1"}])
        self.assertEqual(self.governance.calls[0]["processes"], [{"pid": 11, "gpu_index": 1}])

    async def test_self_check_uses_scoped_snapshot_counts(self):
        payload = await self_check()

        self.assertEqual(payload["data_source"], "cache")
        self.assertEqual(payload["checked_at"], self.snapshot["collected_at"])
        self.assertEqual(payload["gpu_count"], 1)
        self.assertEqual(payload["process_count"], 1)
        gpu_check = next(item for item in payload["checks"] if item["key"] == "gpu")
        process_check = next(item for item in payload["checks"] if item["key"] == "process")
        self.assertIn("1 张真实 GPU", gpu_check["detail"])
        self.assertIn("1 个 GPU 进程", process_check["detail"])


if __name__ == "__main__":
    unittest.main()
