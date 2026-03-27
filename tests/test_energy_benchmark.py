import os
import sys
import time
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.energy_analytics import EnergyAnalytics  # noqa: E402
from app.services.governance import GovernanceService  # noqa: E402


class FakeAgent:
    def __init__(self, gpus=None, processes=None):
        self._gpus = gpus or []
        self._processes = processes or []

    async def get_all_gpus(self):
        return [dict(item) for item in self._gpus]

    async def get_processes(self):
        return [dict(item) for item in self._processes]


class FakeStore:
    async def get_all_task_priorities(self):
        return {
            101: "urgent",
            202: "deferrable",
            303: "normal",
        }

    async def get_user_stats(self):
        now = time.time()
        return [
            {"username": "alice", "earliest_start": now - 8 * 3600},
            {"username": "bob", "earliest_start": now - 2 * 3600},
        ]

    async def get_user_governance_rules(self):
        return {}


class FakeScheduler:
    budget_enabled = True
    budget_limit_watts = 500

    async def run_rules(self, gpus, processes):
        return [
            {
                "action": "set_power_limit",
                "target": {"gpu_index": 0, "power_limit": 240},
                "reason": "规则治理对高功耗低效率 GPU 执行削峰。",
                "estimated_saving_w": 60,
            }
        ]

    async def run_budget_schedule(self, gpus, processes):
        return [
            {
                "action": "pause_task",
                "target": {"pid": 202},
                "reason": "总功率超出预算，暂停可延迟任务。",
                "estimated_saving": 80,
            }
        ]

    async def run_ai_schedule(self, gpus, processes):
        return {
            "actions": [
                {
                    "action": "set_power_limit",
                    "target": {"gpu_index": 1, "power_limit": 180},
                    "reason": "完整治理进一步收缩非满载 GPU 功率上限。",
                    "estimated_saving_w": 40,
                }
            ]
        }

    def get_budget_status(self, gpus):
        total_power = sum(float(item.get("power_usage", 0) or 0) for item in gpus)
        remaining = round(self.budget_limit_watts - total_power, 1)
        return {
            "enabled": self.budget_enabled,
            "total_power_budget": self.budget_limit_watts,
            "current_total_power": round(total_power, 1),
            "remaining_power": remaining,
            "usage_pct": round(total_power / self.budget_limit_watts * 100, 1) if self.budget_limit_watts else 0,
            "is_exceeded": total_power > self.budget_limit_watts,
        }


class EnergyBenchmarkTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        now = time.time()
        self.gpus = [
            {
                "index": 0,
                "power_usage": 310,
                "power_limit": 350,
                "gpu_utilization": 92,
                "temperature": 87,
                "memory_used": 28000,
                "memory_total": 32768,
                "memory_free": 4768,
                "memory_utilization": 85,
            },
            {
                "index": 1,
                "power_usage": 220,
                "power_limit": 300,
                "gpu_utilization": 58,
                "temperature": 72,
                "memory_used": 18000,
                "memory_total": 24576,
                "memory_free": 6576,
                "memory_utilization": 73,
            },
        ]
        self.processes = [
            {
                "pid": 101,
                "username": "alice",
                "name": "python.exe",
                "command": "python train_urgent.py",
                "gpu_index": 0,
                "gpu_memory_used": 12 * 1024 * 1024 * 1024,
                "create_time": now - 6 * 3600,
            },
            {
                "pid": 202,
                "username": "alice",
                "name": "python.exe",
                "command": "python train_deferrable.py",
                "gpu_index": 0,
                "gpu_memory_used": 8 * 1024 * 1024 * 1024,
                "create_time": now - 3 * 3600,
            },
            {
                "pid": 303,
                "username": "bob",
                "name": "python.exe",
                "command": "python train_normal.py",
                "gpu_index": 1,
                "gpu_memory_used": 10 * 1024 * 1024 * 1024,
                "create_time": now - 90 * 60,
            },
        ]
        self.store = FakeStore()
        self.agent = FakeAgent(self.gpus, self.processes)
        self.governance = GovernanceService(self.store, self.agent)
        self.scheduler = FakeScheduler()
        self.analytics = EnergyAnalytics(
            self.store,
            agent_client=self.agent,
            governance_service=self.governance,
        )

    async def test_strategy_benchmark_returns_three_modes(self):
        result = await self.analytics.get_strategy_benchmark(self.scheduler)

        self.assertFalse(result["insufficient_data"])
        self.assertEqual(result["scenario"], "budget_pressure")
        self.assertEqual(len(result["results"]), 3)

        modes = [item["mode"] for item in result["results"]]
        self.assertEqual(modes, ["observe", "rules_only", "full_governance"])
        self.assertIn(result["winner_mode"], modes)

        observe = next(item for item in result["results"] if item["mode"] == "observe")
        full = next(item for item in result["results"] if item["mode"] == "full_governance")
        self.assertGreater(observe["projected_total_power_w"], full["projected_total_power_w"])
        self.assertGreaterEqual(full["action_count"], 2)

    async def test_strategy_benchmark_handles_missing_gpu_data(self):
        analytics = EnergyAnalytics(
            self.store,
            agent_client=FakeAgent([], self.processes),
            governance_service=self.governance,
        )

        result = await analytics.get_strategy_benchmark(self.scheduler)

        self.assertTrue(result["insufficient_data"])
        self.assertIn("真实 GPU", result["message"])


if __name__ == "__main__":
    unittest.main()
