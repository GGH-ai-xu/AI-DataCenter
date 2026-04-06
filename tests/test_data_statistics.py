"""数据统计接口单元测试 - tests/test_data_statistics.py

内存 SQLite 验证 DataStore.get_data_statistics() 的聚合逻辑。
"""

import os
import sys
import time
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.data_store import DataStore  # noqa: E402


class DataStatisticsTests(unittest.IsolatedAsyncioTestCase):
    """验证 get_data_statistics 返回正确的聚合数据"""

    async def asyncSetUp(self):
        self.store = DataStore(":memory:")
        await self.store.init()

    async def asyncTearDown(self):
        await self.store.close()

    # ── 空库 ──────────────────────────────────────────────

    async def test_empty_db_returns_zero_totals(self):
        stats = await self.store.get_data_statistics()
        self.assertEqual(stats["total_records"], 0)
        self.assertIsNone(stats["collection_start"])
        self.assertEqual(stats["collection_duration_hours"], 0)
        self.assertEqual(stats["avg_records_per_hour"], 0)

    async def test_empty_db_has_all_table_keys(self):
        stats = await self.store.get_data_statistics()
        expected_tables = {
            "gpu_history", "process_history", "alerts",
            "schedule_log", "optimization_snapshots", "governance_audit_log",
        }
        self.assertEqual(set(stats["tables"].keys()), expected_tables)
        for info in stats["tables"].values():
            self.assertEqual(info["count"], 0)
            self.assertIn("label", info)

    # ── 含数据 ────────────────────────────────────────────

    async def test_single_table_count(self):
        """插入若干 gpu_history 记录，验证 total 与分表计数"""
        now = time.time()
        db = self.store._db
        for i in range(5):
            await db.execute(
                "INSERT INTO gpu_history (gpu_index, temperature, power_usage, timestamp) VALUES (?, ?, ?, ?)",
                (0, 60, 200.0, now - i * 60),
            )
        await db.commit()

        stats = await self.store.get_data_statistics()
        self.assertEqual(stats["tables"]["gpu_history"]["count"], 5)
        self.assertEqual(stats["total_records"], 5)

    async def test_multiple_tables_sum(self):
        """多表各插入不同数量，total 应为总和"""
        now = time.time()
        db = self.store._db
        # 3 条 gpu_history
        for i in range(3):
            await db.execute(
                "INSERT INTO gpu_history (gpu_index, temperature, power_usage, timestamp) VALUES (0, 60, 200, ?)",
                (now - i * 60,),
            )
        # 2 条 alerts
        for i in range(2):
            await db.execute(
                "INSERT INTO alerts (gpu_index, alert_type, severity, message, value, threshold, timestamp) VALUES (0, 'temp', 'warning', 'test', 80, 85, ?)",
                (now - i * 60,),
            )
        # 1 条 schedule_log
        await db.execute(
            "INSERT INTO schedule_log (action, target, reason, timestamp) VALUES ('cap', 'gpu0', 'budget', ?)",
            (now,),
        )
        await db.commit()

        stats = await self.store.get_data_statistics()
        self.assertEqual(stats["tables"]["gpu_history"]["count"], 3)
        self.assertEqual(stats["tables"]["alerts"]["count"], 2)
        self.assertEqual(stats["tables"]["schedule_log"]["count"], 1)
        self.assertEqual(stats["total_records"], 6)

    async def test_collection_start_is_earliest_timestamp(self):
        """collection_start 应为 gpu_history 最早的 timestamp"""
        db = self.store._db
        base = 1700000000.0
        for i in range(3):
            await db.execute(
                "INSERT INTO gpu_history (gpu_index, temperature, power_usage, timestamp) VALUES (0, 60, 200, ?)",
                (base + i * 3600,),
            )
        await db.commit()

        stats = await self.store.get_data_statistics()
        self.assertAlmostEqual(stats["collection_start"], base, places=0)

    async def test_duration_hours_positive(self):
        """有数据时 collection_duration_hours 应 > 0"""
        now = time.time()
        db = self.store._db
        await db.execute(
            "INSERT INTO gpu_history (gpu_index, temperature, power_usage, timestamp) VALUES (0, 60, 200, ?)",
            (now - 7200,),
        )
        await db.commit()

        stats = await self.store.get_data_statistics()
        self.assertGreaterEqual(stats["collection_duration_hours"], 1.9)

    async def test_avg_records_per_hour(self):
        """验证吞吐率计算 = total / duration_hours"""
        db = self.store._db
        base = time.time() - 3600  # 1 小时前
        for i in range(10):
            await db.execute(
                "INSERT INTO gpu_history (gpu_index, temperature, power_usage, timestamp) VALUES (0, 60, 200, ?)",
                (base + i * 60,),
            )
        await db.commit()

        stats = await self.store.get_data_statistics()
        # ~10 条 / ~1 小时 → 大约 10 条/小时
        self.assertGreater(stats["avg_records_per_hour"], 5)
        self.assertLess(stats["avg_records_per_hour"], 15)

    async def test_table_labels_are_chinese(self):
        """每张表的 label 应为非空中文描述"""
        stats = await self.store.get_data_statistics()
        for info in stats["tables"].values():
            self.assertTrue(len(info["label"]) > 0)

    # ── 未初始化 ──────────────────────────────────────────

    async def test_uninitialized_store_returns_empty(self):
        """_db 为 None 时返回空结果，不报错"""
        uninit = DataStore(":memory:")
        stats = await uninit.get_data_statistics()
        self.assertEqual(stats["total_records"], 0)
        self.assertIsNone(stats["collection_start"])


if __name__ == "__main__":
    unittest.main()
