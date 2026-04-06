import os
import sys
import types
import unittest
from unittest import mock


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.api.scheduler import build_fallback_report, generate_report  # noqa: E402
from app.services.privacy import PrivacyService  # noqa: E402
from app.services.scheduler import SchedulerEngine  # noqa: E402


class FakeAgent:
    def __init__(self):
        self.calls = []

    async def set_power_limit(self, gpu_index, power_limit):
        self.calls.append(("set_power_limit", gpu_index, power_limit))
        return {"success": True}

    async def pause_task(self, pid):
        self.calls.append(("pause_task", pid))
        return {"success": True}

    async def resume_task(self, pid):
        self.calls.append(("resume_task", pid))
        return {"success": True}


class FakeStore:
    def __init__(self):
        self.logs = []

    async def save_schedule_log(
        self,
        action,
        target,
        reason,
        result="",
        gpu_indexes=None,
    ):
        self.logs.append((action, target, reason, result, gpu_indexes))

    async def get_all_task_priorities(self):
        return {}


class FakeLLM:
    def __init__(self):
        self.task_data = None

    async def generate_schedule(self, gpu_data, task_data, time_period):
        self.task_data = task_data
        return {"actions": [], "summary": "ok", "estimated_power_saving": 0}


class FakeReportStore:
    async def get_power_summary(self, hours):
        return {
            "hours": hours,
            "gpus": [{"gpu_index": 0, "avg_power": 150, "max_power": 220, "min_power": 90, "samples": 20}],
            "total_avg_power": 150,
        }

    async def get_alerts(self, limit=20):
        return []


class SchedulerEngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_execute_actions_calls_agent_and_logs_without_rehearsal_mode(self):
        agent = FakeAgent()
        store = FakeStore()
        scheduler = SchedulerEngine(agent, store)

        results = await scheduler.execute_actions(
            [
                {
                    "action": "set_power_limit",
                    "target": {"gpu_index": 0, "power_limit": 200},
                    "reason": "test",
                }
            ]
        )

        self.assertTrue(results[0]["success"])
        self.assertNotIn("dry_run", results[0])
        self.assertEqual(agent.calls, [("set_power_limit", 0, 200)])
        self.assertEqual(len(store.logs), 1)

    async def test_execute_actions_real_calls_agent_and_logs(self):
        agent = FakeAgent()
        store = FakeStore()
        scheduler = SchedulerEngine(agent, store)

        results = await scheduler.execute_actions(
            [
                {
                    "action": "pause_task",
                    "target": {"pid": 123},
                    "reason": "test",
                }
            ],
        )

        self.assertTrue(results[0]["success"])
        self.assertEqual(agent.calls, [("pause_task", 123)])
        self.assertEqual(len(store.logs), 1)

    async def test_run_ai_schedule_uses_sanitized_processes(self):
        agent = FakeAgent()
        store = FakeStore()
        llm = FakeLLM()
        privacy = PrivacyService()
        scheduler = SchedulerEngine(agent, store, llm_service=llm, privacy_service=privacy)

        await scheduler.run_ai_schedule(
            [{"index": 0, "power_usage": 120, "power_limit": 140}],
            [
                {
                    "pid": 321,
                    "username": "alice",
                    "command": r"C:\Users\alice\project\train.py",
                    "priority": "normal",
                }
            ],
        )

        self.assertIsNotNone(llm.task_data)
        self.assertNotEqual(llm.task_data[0]["username"], "alice")
        self.assertIn("[path]", llm.task_data[0]["command"])

    async def test_build_fallback_report_contains_summary_and_recommendations(self):
        report = build_fallback_report(
            {
                "hours": 24,
                "gpus": [
                    {"gpu_index": 0, "avg_power": 240, "max_power": 320, "min_power": 120, "samples": 100},
                    {"gpu_index": 1, "avg_power": 120, "max_power": 180, "min_power": 60, "samples": 100},
                ],
                "total_avg_power": 360,
            },
            [
                {
                    "gpu_index": 0,
                    "alert_type": "temperature",
                    "severity": "critical",
                    "message": "GPU0 温度过高",
                    "timestamp": 1710000000,
                }
            ],
        )

        self.assertIn("调度能耗分析报告（基础版）", report)
        self.assertIn("集群平均总功率：360.0W", report)
        self.assertIn("温度类告警：1 条", report)
        self.assertIn("建议动作", report)
        self.assertIn("预估节能潜力", report)

    async def test_build_fallback_report_handles_empty_gpu_history(self):
        report = build_fallback_report(
            {
                "hours": 24,
                "gpus": [],
                "total_avg_power": 0,
            },
            [],
        )

        self.assertIn("当前统计窗口内暂无 GPU 历史样本", report)
        self.assertIn("当前数据不足，暂不输出节能估算", report)

    async def test_generate_report_returns_fallback_when_llm_missing(self):
        fake_main = types.SimpleNamespace(
            app_state=types.SimpleNamespace(
                llm=None,
                store=FakeReportStore(),
            )
        )

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            response = await generate_report()

        self.assertEqual(response["source"], "fallback")
        self.assertIn("调度能耗分析报告（基础版）", response["report"])


# ========== Phase 2A: 调度引擎核心逻辑测试 ==========


class SchedulerRulesTests(unittest.IsolatedAsyncioTestCase):
    """规则引擎测试"""

    def _make_engine(self, budget=1200, budget_enabled=False):
        return SchedulerEngine(
            FakeAgent(), FakeStore(),
            budget_limit_watts=budget,
            budget_enabled=budget_enabled,
        )

    async def test_run_rules_thermal_emergency_90c(self):
        """≥90°C 触发紧急降频到 200W"""
        engine = self._make_engine()
        gpus = [{"index": 0, "temperature": 92, "power_usage": 300, "power_limit": 350}]
        actions = await engine.run_rules(gpus, [])
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["target"]["power_limit"], 200)
        self.assertEqual(actions[0]["rule"], "emergency_thermal")

    async def test_run_rules_thermal_warning_85c(self):
        """≥85°C 且 <90°C 触发预防降频到 250W"""
        engine = self._make_engine()
        gpus = [{"index": 0, "temperature": 87, "power_usage": 300, "power_limit": 350}]
        actions = await engine.run_rules(gpus, [])
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["target"]["power_limit"], 250)
        self.assertEqual(actions[0]["rule"], "thermal_warning")

    async def test_run_rules_no_action_below_threshold(self):
        """温度正常时无动作"""
        engine = self._make_engine()
        gpus = [{"index": 0, "temperature": 70, "power_usage": 250, "power_limit": 350}]
        actions = await engine.run_rules(gpus, [])
        self.assertEqual(len(actions), 0)

    async def test_run_rules_multiple_gpus(self):
        """多 GPU 各自独立触发规则"""
        engine = self._make_engine()
        gpus = [
            {"index": 0, "temperature": 91, "power_usage": 300, "power_limit": 350},
            {"index": 1, "temperature": 86, "power_usage": 280, "power_limit": 350},
            {"index": 2, "temperature": 70, "power_usage": 200, "power_limit": 350},
        ]
        actions = await engine.run_rules(gpus, [])
        self.assertEqual(len(actions), 2)
        limits = {a["target"]["gpu_index"]: a["target"]["power_limit"] for a in actions}
        self.assertEqual(limits[0], 200)  # 紧急
        self.assertEqual(limits[1], 250)  # 警告


class SchedulerBudgetTests(unittest.IsolatedAsyncioTestCase):
    """预算调度测试"""

    def _make_engine(self, budget=800, budget_enabled=True):
        agent = FakeAgent()
        store = FakeStore()
        return SchedulerEngine(
            agent, store,
            budget_limit_watts=budget,
            budget_enabled=budget_enabled,
        )

    async def test_budget_over_budget_caps_power(self):
        """超预算时生成功率限制动作"""
        engine = self._make_engine(budget=500, budget_enabled=True)
        gpus = [
            {"index": 0, "power_usage": 300, "power_limit": 350, "gpu_utilization": 40},
            {"index": 1, "power_usage": 280, "power_limit": 350, "gpu_utilization": 60},
        ]
        # 总功耗 580W > 预算 500W
        processes = [
            {"pid": 100, "gpu_index": 0, "priority": "normal", "username": "alice"},
            {"pid": 200, "gpu_index": 1, "priority": "normal", "username": "bob"},
        ]
        actions = await engine.run_budget_schedule(gpus, processes)
        power_limit_actions = [a for a in actions if a["action"] == "set_power_limit"]
        self.assertGreater(len(power_limit_actions), 0, "超预算应生成功率限制")

    async def test_budget_pauses_deferrable_first(self):
        """暂停时优先暂停 deferrable 任务"""
        engine = self._make_engine(budget=400, budget_enabled=True)
        gpus = [
            {"index": 0, "power_usage": 300, "power_limit": 350, "gpu_utilization": 90},
            {"index": 1, "power_usage": 300, "power_limit": 350, "gpu_utilization": 90},
        ]
        # 总功耗 600W >> 预算 400W，功率限制不够，需暂停
        processes = [
            {"pid": 100, "gpu_index": 0, "priority": "deferrable", "username": "alice"},
            {"pid": 200, "gpu_index": 1, "priority": "normal", "username": "bob"},
        ]
        actions = await engine.run_budget_schedule(gpus, processes)
        pause_actions = [a for a in actions if a["action"] == "pause_task"]
        if pause_actions:
            # 第一个被暂停的应是 deferrable
            first_paused_pid = pause_actions[0]["target"]["pid"]
            self.assertEqual(first_paused_pid, 100,
                             "deferrable 任务应优先被暂停")

    async def test_budget_under_budget_restores(self):
        """低于预算-余量时恢复原功率"""
        engine = self._make_engine(budget=1000, budget_enabled=True)
        # 模拟之前被预算管理压缩过
        engine._budget_managed_limits = {0: 350, 1: 350}
        gpus = [
            {"index": 0, "power_usage": 200, "power_limit": 250, "gpu_utilization": 50},
            {"index": 1, "power_usage": 180, "power_limit": 250, "gpu_utilization": 40},
        ]
        # 总功耗 380W << 预算 1000W - 余量
        actions = await engine.run_budget_schedule(gpus, [])
        restore_actions = [a for a in actions if a.get("rule") == "restore_budget_cap"]
        self.assertGreater(len(restore_actions), 0, "低于预算时应恢复功率")

    async def test_budget_disabled_returns_restore_only(self):
        """预算禁用时只返回恢复动作"""
        engine = self._make_engine(budget=500, budget_enabled=False)
        engine._budget_managed_limits = {0: 350}
        gpus = [
            {"index": 0, "power_usage": 300, "power_limit": 250, "gpu_utilization": 80},
        ]
        actions = await engine.run_budget_schedule(gpus, [])
        for a in actions:
            self.assertEqual(a.get("rule"), "restore_budget_cap",
                             "禁用预算时只应恢复")


class SchedulerCarbonTests(unittest.TestCase):
    """碳预算测试"""

    def _make_engine(self):
        return SchedulerEngine(FakeAgent(), FakeStore())

    def test_carbon_budget_status_basic(self):
        """碳预算状态基本计算"""
        engine = self._make_engine()
        engine.configure_carbon_budget(True, 50.0)
        engine._carbon_accumulated_wh = 5000  # 5kWh
        gpus = [{"power_usage": 300}, {"power_usage": 200}]
        status = engine.get_carbon_budget_status(gpus)

        self.assertTrue(status["enabled"])
        self.assertAlmostEqual(status["accumulated_kwh"], 5.0, places=1)
        expected_co2 = 5.0 * 0.5703
        self.assertAlmostEqual(status["accumulated_carbon_kg"], expected_co2, places=2)
        self.assertEqual(status["current_power_w"], 500.0)

    def test_carbon_budget_exceeded(self):
        """碳预算超标检测"""
        engine = self._make_engine()
        engine.configure_carbon_budget(True, 10.0)
        # 设置累积值使碳排放超过 10kgCO2
        # 10 / 0.5703 ≈ 17.53 kWh = 17530 Wh
        engine._carbon_accumulated_wh = 18000
        status = engine.get_carbon_budget_status([])
        self.assertTrue(status["is_exceeded"])
        self.assertGreater(status["usage_pct"], 100)


class SchedulerExecuteValidationTests(unittest.IsolatedAsyncioTestCase):
    """动作执行验证测试"""

    async def test_rejects_power_limit_out_of_range(self):
        """功率超出 100-350W 范围被拒绝"""
        engine = SchedulerEngine(FakeAgent(), FakeStore())
        results = await engine.execute_actions([
            {"action": "set_power_limit", "target": {"gpu_index": 0, "power_limit": 50}},
            {"action": "set_power_limit", "target": {"gpu_index": 0, "power_limit": 400}},
        ])
        for r in results:
            self.assertFalse(r["success"])
            self.assertIn("error", r)

    async def test_rejects_invalid_pid(self):
        """无效 PID 被拒绝"""
        engine = SchedulerEngine(FakeAgent(), FakeStore())
        results = await engine.execute_actions([
            {"action": "pause_task", "target": {"pid": -1}},
            {"action": "pause_task", "target": {"pid": 0}},
        ])
        for r in results:
            self.assertFalse(r["success"])

    async def test_rejects_unknown_action(self):
        """未知动作类型被拒绝"""
        engine = SchedulerEngine(FakeAgent(), FakeStore())
        results = await engine.execute_actions([
            {"action": "delete_gpu", "target": {}},
        ])
        self.assertFalse(results[0]["success"])
        self.assertIn("未知", results[0]["error"])

    async def test_tracks_managed_limits_on_budget_cap(self):
        """预算限功率成功后记录 managed_limits"""
        agent = FakeAgent()
        store = FakeStore()
        engine = SchedulerEngine(agent, store)
        results = await engine.execute_actions([
            {
                "action": "set_power_limit",
                "target": {"gpu_index": 0, "power_limit": 200},
                "reason": "预算压缩",
                "rule": "power_budget_cap",
                "original_power_limit": 350,
            },
        ])
        self.assertTrue(results[0]["success"])
        self.assertIn(0, engine._budget_managed_limits)
        self.assertEqual(engine._budget_managed_limits[0], 350)


class SchedulerTickTests(unittest.IsolatedAsyncioTestCase):
    """Tick 编排测试"""

    async def test_tick_accumulates_carbon(self):
        """tick 累加碳预算 Wh"""
        engine = SchedulerEngine(FakeAgent(), FakeStore())
        engine._carbon_budget_enabled = True
        engine._carbon_accumulated_wh = 0.0
        gpus = [{"power_usage": 300, "index": 0, "temperature": 60}]
        await engine.tick(gpus, [])
        # 300W * 2s / 3600 ≈ 0.1667 Wh
        self.assertGreater(engine._carbon_accumulated_wh, 0.1)

    async def test_tick_executes_rules(self):
        """tick 中规则引擎正常触发"""
        agent = FakeAgent()
        store = FakeStore()
        engine = SchedulerEngine(agent, store)
        gpus = [{"index": 0, "temperature": 91, "power_usage": 300, "power_limit": 350}]
        result = await engine.tick(gpus, [])
        self.assertGreater(len(result["rule_actions"]), 0)
        self.assertGreater(len(result["executed"]), 0)


if __name__ == "__main__":
    unittest.main()
