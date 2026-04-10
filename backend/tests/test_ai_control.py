"""goal_runtime 控制启发式与调度辅助测试"""

import unittest

from app.services.goal_runtime.control_heuristics import (
    SUPPORTED_ACTIONS,
    _find_budget_value,
    _find_gpu_index,
    _find_pid,
    _find_power_limit,
    _priority_from_text,
    _priority_label,
    _to_int,
    build_control_heuristic,
)
from app.services.goal_runtime.schedule_once import run_schedule_once


class TestToInt(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(_to_int(42), 42)
        self.assertEqual(_to_int("123"), 123)

    def test_invalid(self):
        self.assertEqual(_to_int(None, -1), -1)
        self.assertEqual(_to_int("abc", 0), 0)
        self.assertEqual(_to_int("", 5), 5)


class TestPriorityHelpers(unittest.TestCase):
    def test_priority_from_text(self):
        self.assertEqual(_priority_from_text("紧急任务"), "urgent")
        self.assertEqual(_priority_from_text("可延迟"), "deferrable")
        self.assertEqual(_priority_from_text("Normal"), "normal")
        self.assertIsNone(_priority_from_text("random"))

    def test_priority_label(self):
        self.assertEqual(_priority_label("urgent"), "紧急")
        self.assertEqual(_priority_label("normal"), "普通")
        self.assertEqual(_priority_label("deferrable"), "可延迟")
        self.assertEqual(_priority_label(None), "未知")


class TestExtractionHelpers(unittest.TestCase):
    def test_find_pid(self):
        self.assertEqual(_find_pid("暂停进程：12345"), 12345)
        self.assertEqual(_find_pid("PID 6789"), 6789)
        self.assertIsNone(_find_pid("暂停所有任务"))

    def test_find_gpu_index(self):
        self.assertEqual(_find_gpu_index("GPU 0"), 0)
        self.assertEqual(_find_gpu_index("显卡 2"), 2)
        self.assertIsNone(_find_gpu_index("no gpu here"))

    def test_find_power_limit(self):
        self.assertEqual(_find_power_limit("设到250W"), 250)
        self.assertEqual(_find_power_limit("设到300瓦"), 300)
        self.assertIsNone(_find_power_limit("设到50W"))

    def test_find_budget_value(self):
        self.assertEqual(_find_budget_value("总功率预算设为1200W"), 1200)
        self.assertEqual(_find_budget_value("预算 800 瓦"), 800)
        self.assertIsNone(_find_budget_value("随便设一下"))


class TestBuildControlHeuristic(unittest.TestCase):
    def test_supported_actions_have_labels(self):
        self.assertIn("set_power_limit", SUPPORTED_ACTIONS)
        self.assertIn("pause_task", SUPPORTED_ACTIONS)
        self.assertIn("run_schedule_once", SUPPORTED_ACTIONS)

    def test_extracts_pause_action(self):
        plan = build_control_heuristic("暂停 PID 1234")

        self.assertEqual(plan["actions"][0]["action"], "pause_task")

    def test_extracts_schedule_action(self):
        plan = build_control_heuristic("执行调度一次")

        self.assertEqual(plan["actions"][0]["action"], "run_schedule_once")

    def test_extracts_power_limit_and_budget(self):
        plan = build_control_heuristic("把 GPU 0 功耗上限设到250W，并把总功率预算设为1200W")
        action_names = [item["action"] for item in plan["actions"]]

        self.assertIn("set_power_limit", action_names)
        self.assertIn("configure_budget", action_names)

    def test_returns_warning_when_no_action(self):
        plan = build_control_heuristic("今天天气怎么样")

        self.assertEqual(plan["actions"], [])
        self.assertTrue(plan["warnings"])


class FakeAgent:
    async def get_all_gpus(self):
        return [{"index": 0, "name": "GPU 0"}]

    async def get_processes(self):
        return [{"pid": 1234, "gpu_index": 0}]


class EmptyAgent(FakeAgent):
    async def get_all_gpus(self):
        return []


class FakeImportContext:
    def filter_gpus(self, gpus):
        return gpus

    def filter_processes(self, processes):
        return processes


class FakeScheduler:
    async def run_rules(self, gpus, processes):
        return [{"action": "rule", "gpus": len(gpus), "processes": len(processes)}]

    async def execute_actions(self, actions):
        return [{"success": True, "count": len(actions)}]

    async def run_budget_schedule(self, gpus, processes):
        return [{"action": "budget", "gpus": len(gpus), "processes": len(processes)}]

    async def run_ai_schedule(self, gpus, processes):
        return {"actions": [{"action": "ai", "gpus": len(gpus), "processes": len(processes)}]}


class FakeAppState:
    def __init__(self, agent):
        self.agent = agent
        self.import_context = FakeImportContext()
        self.scheduler = FakeScheduler()


class TestRunScheduleOnce(unittest.IsolatedAsyncioTestCase):
    async def test_run_schedule_once_returns_combined_results(self):
        result = await run_schedule_once(FakeAppState(FakeAgent()))

        self.assertTrue(result["success"])
        self.assertEqual(result["rule_results"][0]["count"], 1)
        self.assertEqual(result["budget_results"][0]["count"], 1)
        self.assertEqual(result["ai_results"][0]["count"], 1)

    async def test_run_schedule_once_returns_error_when_scope_has_no_gpu(self):
        result = await run_schedule_once(FakeAppState(EmptyAgent()))

        self.assertFalse(result["success"])
        self.assertIn("GPU", result["error"])


if __name__ == "__main__":
    unittest.main()
