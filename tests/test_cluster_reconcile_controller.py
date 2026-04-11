import asyncio
import os
import sys
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.cluster_control.reconcile_controller import (  # noqa: E402
    ClusterReconcileController,
)


class ClusterReconcileControllerTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_once_skips_when_runtime_not_connected(self):
        calls = []

        async def runtime_status_reader():
            return {"status": "invalid"}

        async def nodes_loader():
            calls.append("nodes")
            return []

        async def reconcile_runner(nodes):
            calls.append(("reconcile", nodes))
            return {"dispatched": 1}

        controller = ClusterReconcileController(
            nodes_loader=nodes_loader,
            reconcile_runner=reconcile_runner,
            runtime_status_reader=runtime_status_reader,
            interval_seconds=0.05,
            enabled=False,
        )

        summary = await controller.run_once(trigger="manual")

        self.assertTrue(summary["skipped"])
        self.assertEqual(summary["skip_reason"], "runtime status: invalid")
        self.assertEqual(calls, [])
        self.assertEqual(controller.snapshot()["last_skip_reason"], "runtime status: invalid")

    async def test_background_loop_runs_when_enabled(self):
        ticks = []

        async def runtime_status_reader():
            return {"status": "connected"}

        async def nodes_loader():
            return [{"node_id": "node-a"}]

        async def reconcile_runner(nodes):
            ticks.append(tuple(item["node_id"] for item in nodes))
            return {"processed": 1, "dispatched": 1}

        controller = ClusterReconcileController(
            nodes_loader=nodes_loader,
            reconcile_runner=reconcile_runner,
            runtime_status_reader=runtime_status_reader,
            interval_seconds=0.02,
            enabled=True,
        )

        controller.start()
        await asyncio.sleep(0.07)
        await controller.shutdown()

        self.assertGreaterEqual(len(ticks), 2)
        snapshot = controller.snapshot()
        self.assertTrue(snapshot["enabled"])
        self.assertGreaterEqual(snapshot["tick_count"], 2)
        self.assertEqual(snapshot["last_summary"]["dispatched"], 1)


if __name__ == "__main__":
    unittest.main()
