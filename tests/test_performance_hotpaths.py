import asyncio
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app import main as backend_main  # noqa: E402
from app.services.data_store import DataStore  # noqa: E402
from app.ws.realtime import ConnectionManager  # noqa: E402


def build_gpu_snapshot(index: int, timestamp: float) -> dict:
    return {
        "index": index,
        "temperature": 70,
        "power_usage": 210.0,
        "power_limit": 250.0,
        "gpu_utilization": 60,
        "memory_utilization": 40,
        "memory_used": 12 * 1024 * 1024,
        "memory_total": 24 * 1024 * 1024,
        "fan_speed": 35,
        "timestamp": timestamp,
    }


class BackendPerformanceStructureTests(unittest.TestCase):
    def test_data_store_removes_old_hotspot_patterns(self):
        text = (ROOT / "backend/app/services/data_store.py").read_text(encoding="utf-8")

        self.assertIn("save_collection_cycle", text)
        self.assertNotIn("SELECT id FROM process_history WHERE pid = ?", text)
        self.assertNotIn("while bucket_ts <= final_bucket", text)


class CollectSnapshotTests(unittest.IsolatedAsyncioTestCase):
    async def test_collect_agent_snapshot_runs_agent_reads_concurrently(self):
        collect_agent_snapshot = getattr(backend_main, "collect_agent_snapshot")

        class FakeAgent:
            async def get_all_gpus(self):
                await asyncio.sleep(0.05)
                return [{"index": 0}]

            async def get_system_info(self):
                await asyncio.sleep(0.05)
                return {"cpu_percent": 12.5}

            async def get_processes(self):
                await asyncio.sleep(0.05)
                return [{"pid": 11, "gpu_index": 0}]

        started = time.perf_counter()
        snapshot = await collect_agent_snapshot(FakeAgent())
        elapsed = time.perf_counter() - started

        self.assertEqual(snapshot["gpus"][0]["index"], 0)
        self.assertEqual(snapshot["processes"][0]["pid"], 11)
        self.assertLess(elapsed, 0.13)


class DataStoreBatchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tempdir.name, "perf.db")
        self.store = DataStore(self.db_path)
        await self.store.init()

    async def asyncTearDown(self):
        await self.store.close()
        self.tempdir.cleanup()

    async def test_data_store_enables_sqlite_lock_mitigation_pragmas(self):
        journal_mode_cursor = await self.store._db.execute("PRAGMA journal_mode;")
        busy_timeout_cursor = await self.store._db.execute("PRAGMA busy_timeout;")
        synchronous_cursor = await self.store._db.execute("PRAGMA synchronous;")

        journal_mode = (await journal_mode_cursor.fetchone())[0]
        busy_timeout = (await busy_timeout_cursor.fetchone())[0]
        synchronous = (await synchronous_cursor.fetchone())[0]

        self.assertEqual(str(journal_mode).lower(), "wal")
        self.assertGreaterEqual(int(busy_timeout), 30000)
        self.assertEqual(int(synchronous), 1)

    async def test_save_collection_cycle_persists_snapshot_processes_and_alerts(self):
        save_collection_cycle = getattr(self.store, "save_collection_cycle")
        now = 1_700_000_000.0
        alerts = [
            {
                "gpu_index": 0,
                "alert_type": "temperature",
                "severity": "warning",
                "message": "GPU0 温度偏高",
                "value": 88,
                "threshold": 85,
                "timestamp": now,
            },
            {
                "gpu_index": 0,
                "alert_type": "power",
                "severity": "critical",
                "message": "GPU0 功耗过高",
                "value": 320,
                "threshold": 300,
                "timestamp": now + 1,
            },
        ]

        with mock.patch("app.services.data_store.time.time", return_value=now):
            await save_collection_cycle(
                [build_gpu_snapshot(0, now)],
                [
                    {
                        "pid": 42,
                        "gpu_index": 0,
                        "username": "alice",
                        "command": "python train.py",
                        "gpu_memory_used": 1024,
                    }
                ],
                alerts,
            )

        latest = await self.store.get_all_gpu_latest()
        with mock.patch("app.services.data_store.time.time", return_value=now):
            timeline = await self.store.get_process_timeline(1)
        saved_alerts = await self.store.get_alerts(limit=10)

        self.assertEqual(len(latest), 1)
        self.assertEqual(timeline[0]["pid"], 42)
        self.assertEqual(len(saved_alerts), 2)

    async def test_get_replay_frames_counts_active_tasks_and_users(self):
        now = 1_700_000_000.0
        await self.store._db.executemany(
            """INSERT INTO process_history
               (pid, gpu_index, username, command, gpu_memory_used, first_seen, last_seen, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (101, 0, "alice", "python a.py", 100, now, now + 3600, 0),
                (202, 1, "bob", "python b.py", 100, now + 1800, now + 5400, 0),
                (303, 1, "alice", "python c.py", 100, now + 3600, now + 5400, 0),
            ],
        )
        await self.store._db.commit()

        with mock.patch("app.services.data_store.time.time", return_value=now + 7200):
            frames = await self.store.get_replay_frames(hours=2, bucket_minutes=30)

        task_counts = [frame["active_task_count"] for frame in frames[:5]]
        user_counts = [frame["active_user_count"] for frame in frames[:5]]

        self.assertEqual(task_counts, [1, 2, 3, 2, 0])
        self.assertEqual(user_counts, [1, 2, 2, 2, 0])


class BroadcastTests(unittest.IsolatedAsyncioTestCase):
    async def test_broadcast_sends_to_connections_concurrently(self):
        manager = ConnectionManager()

        class FakeSocket:
            def __init__(self):
                self.messages = []

            async def send_text(self, message):
                await asyncio.sleep(0.05)
                self.messages.append(message)

        sockets = [FakeSocket(), FakeSocket(), FakeSocket()]
        manager._connections = {
            "user:1": set(sockets),
            "user:2": {FakeSocket()},
        }

        started = time.perf_counter()
        await manager.broadcast("user:1", {"type": "realtime", "gpus": []})
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.13)
        self.assertTrue(all(socket.messages for socket in sockets))

    async def test_broadcast_only_reaches_current_workspace_connections(self):
        manager = ConnectionManager()

        class FakeSocket:
            def __init__(self):
                self.messages = []

            async def send_text(self, message):
                self.messages.append(message)

        mine = FakeSocket()
        other = FakeSocket()
        manager._connections = {
            "user:1": {mine},
            "user:2": {other},
        }

        await manager.broadcast("user:1", {"type": "runtime"})

        self.assertEqual(len(mine.messages), 1)
        self.assertEqual(other.messages, [])


if __name__ == "__main__":
    unittest.main()
