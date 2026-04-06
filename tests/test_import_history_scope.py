import os
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

from fastapi import HTTPException


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.api.alerts import acknowledge_alert  # noqa: E402
from app.services.data_store import DataStore  # noqa: E402


class ImportHistoryScopeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tempdir.name, "history.db")
        self.store = DataStore(self.db_path)
        await self.store.init()
        now = time.time()

        await self.store.save_gpu_snapshot(
            [
                {
                    "index": 0,
                    "temperature": 60,
                    "power_usage": 200,
                    "power_limit": 320,
                    "gpu_utilization": 80,
                    "memory_utilization": 50,
                    "memory_used": 4096,
                    "memory_total": 24564,
                    "fan_speed": 30,
                    "timestamp": now,
                },
                {
                    "index": 1,
                    "temperature": 55,
                    "power_usage": 150,
                    "power_limit": 320,
                    "gpu_utilization": 60,
                    "memory_utilization": 40,
                    "memory_used": 2048,
                    "memory_total": 24564,
                    "fan_speed": 25,
                    "timestamp": now,
                },
            ]
        )
        await self.store.track_processes(
            [
                {
                    "pid": 101,
                    "gpu_index": 0,
                    "username": "alice",
                    "command": "train_a.py",
                    "gpu_memory_used": 4096,
                },
                {
                    "pid": 202,
                    "gpu_index": 1,
                    "username": "bob",
                    "command": "train_b.py",
                    "gpu_memory_used": 2048,
                },
            ],
            timestamp=now,
        )
        self.alert_zero_id = await self.store.save_alert(
            {
                "gpu_index": 0,
                "alert_type": "temperature",
                "severity": "warning",
                "message": "GPU0 hot",
                "value": 88,
                "threshold": 85,
                "timestamp": now,
            }
        )
        self.alert_one_id = await self.store.save_alert(
            {
                "gpu_index": 1,
                "alert_type": "power",
                "severity": "warning",
                "message": "GPU1 high power",
                "value": 280,
                "threshold": 250,
                "timestamp": now,
            }
        )
        await self.store.save_schedule_log(
            "set_power_limit",
            '{"gpu_index": 0, "power_limit": 220}',
            "scope zero",
            "success",
            gpu_indexes=[0],
        )
        await self.store.save_schedule_log(
            "set_power_limit",
            '{"gpu_index": 1, "power_limit": 200}',
            "scope one",
            "success",
            gpu_indexes=[1],
        )
        await self.store.save_optimization_snapshot(
            {
                "baseline_power": 200,
                "optimized_power": 140,
                "saving_pct": 30,
                "co2_saved_kg": 0.03,
                "actions_json": "[]",
                "scope_gpu_indexes": [0],
            }
        )
        await self.store.save_optimization_snapshot(
            {
                "baseline_power": 150,
                "optimized_power": 120,
                "saving_pct": 20,
                "co2_saved_kg": 0.02,
                "actions_json": "[]",
                "scope_gpu_indexes": [1],
            }
        )

    async def asyncTearDown(self):
        await self.store.close()
        self.tempdir.cleanup()

    async def test_power_summary_accepts_gpu_scope(self):
        summary = await self.store.get_power_summary(hours=1, gpu_indexes=[1])

        self.assertEqual([item["gpu_index"] for item in summary["gpus"]], [1])
        self.assertEqual(round(summary["total_avg_power"], 1), 150.0)

    async def test_alerts_accept_gpu_scope(self):
        alerts = await self.store.get_alerts(limit=10, gpu_indexes=[0])

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["gpu_index"], 0)

    async def test_process_timeline_accepts_gpu_scope(self):
        timeline = await self.store.get_process_timeline(hours=1, gpu_indexes=[1])

        self.assertEqual([item["pid"] for item in timeline], [202])

    async def test_schedule_history_accepts_exact_scope(self):
        logs = await self.store.get_schedule_history(hours=1, limit=10, gpu_indexes=[1])

        self.assertEqual([item["reason"] for item in logs], ["scope one"])

    async def test_optimization_history_accepts_exact_scope(self):
        history = await self.store.get_optimization_history(hours=1, gpu_indexes=[0])

        self.assertEqual(len(history), 1)
        self.assertEqual(round(history[0]["optimized_power"], 1), 140.0)

    async def test_replay_frames_accept_gpu_scope(self):
        frames = await self.store.get_replay_frames(hours=1, bucket_minutes=10, gpu_indexes=[0])

        active = [item for item in frames if item["gpu_count"]]
        self.assertTrue(active)
        self.assertEqual(active[0]["gpu_count"], 1)
        self.assertEqual(round(active[0]["avg_power"], 1), 200.0)


class AlertRouteScopeTests(unittest.IsolatedAsyncioTestCase):
    async def test_acknowledge_alert_rejects_out_of_scope_alert(self):
        fake_store = types.SimpleNamespace(
            get_alert_by_id=mock.AsyncMock(return_value={"id": 9, "gpu_index": 7}),
            acknowledge_alert=mock.AsyncMock(),
        )

        class FakeImportContext:
            def ensure_gpu_allowed(self, gpu_index: int):
                raise ValueError(f"GPU {gpu_index} 不在当前导入范围内，请重新导入管理卡")

        fake_main = types.SimpleNamespace(
            app_state=types.SimpleNamespace(
                store=fake_store,
                import_context=FakeImportContext(),
            )
        )

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            with self.assertRaises(HTTPException) as ctx:
                await acknowledge_alert(9)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("当前导入范围内", ctx.exception.detail)
        fake_store.acknowledge_alert.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
