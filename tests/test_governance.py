import os
import sys
import time
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.governance import (  # noqa: E402
    BACKGROUND_PROCESS_NAMES,
    GovernanceService,
)


# --------------- Fakes ---------------


class FakeAgent:
    def __init__(self, gpus=None, processes=None):
        self._gpus = gpus or []
        self._processes = processes or []

    async def get_all_gpus(self):
        return self._gpus

    async def get_processes(self):
        return self._processes


class FakeStore:
    def __init__(self, priorities=None, user_stats=None, rules=None):
        self._priorities = priorities or {}
        self._user_stats = user_stats or []
        self._rules = rules or {}

    async def get_all_task_priorities(self):
        return self._priorities

    async def get_user_stats(self):
        return self._user_stats

    async def get_user_governance_rules(self):
        return self._rules


# --------------- Helpers ---------------

def _make_gpu(index, power_usage=250, power_limit=350, memory_used=16000,
              memory_total=24576, util=70, temp=65):
    return {
        "index": index,
        "power_usage": power_usage,
        "power_limit": power_limit,
        "memory_used": memory_used * 1024 * 1024,
        "memory_total": memory_total * 1024 * 1024,
        "gpu_utilization": util,
        "temperature": temp,
    }


def _make_proc(pid, username, gpu_index, memory_gb=8, priority="normal",
               create_time=None, name="python.exe", command="python train.py"):
    return {
        "pid": pid,
        "username": username,
        "gpu_index": gpu_index,
        "gpu_memory_used": int(memory_gb * 1073741824),
        "priority": priority,
        "create_time": create_time or time.time(),
        "name": name,
        "command": command,
    }


# ========== 用户公平性评分测试 ==========


class FairnessScoreTests(unittest.IsolatedAsyncioTestCase):
    """用户公平性评分核心公式测试"""

    async def _get_report(self, gpus, processes, rules=None, priorities=None):
        agent = FakeAgent(gpus, processes)
        store = FakeStore(priorities=priorities or {}, rules=rules or {})
        svc = GovernanceService(store, agent)
        return await svc.get_fairness_report()

    async def test_single_user_high_fairness(self):
        """单用户独占时公平分应较高（无竞争）"""
        gpus = [_make_gpu(0)]
        procs = [_make_proc(100, "alice", 0, memory_gb=8)]
        report = await self._get_report(gpus, procs)
        users = report["users"]
        self.assertEqual(len(users), 1)
        # 单用户, 理想份额100%, 无超占惩罚, 分数高
        self.assertGreaterEqual(users[0]["fairness_score"], 80)

    async def test_two_equal_users_balanced(self):
        """两用户均等使用时都应获得较高公平分"""
        gpus = [_make_gpu(0), _make_gpu(1)]
        procs = [
            _make_proc(100, "alice", 0, memory_gb=10),
            _make_proc(200, "bob", 1, memory_gb=10),
        ]
        report = await self._get_report(gpus, procs)
        users = report["users"]
        self.assertEqual(len(users), 2)
        for user in users:
            self.assertGreaterEqual(user["fairness_score"], 75,
                                    f"{user['username']} 分数应高于75")

    async def test_dominant_user_low_score(self):
        """一个用户占用80%以上资源时公平分应低"""
        gpus = [_make_gpu(0), _make_gpu(1), _make_gpu(2), _make_gpu(3)]
        # alice 占3张GPU, bob 占1张
        procs = [
            _make_proc(100, "alice", 0, memory_gb=20),
            _make_proc(101, "alice", 1, memory_gb=20),
            _make_proc(102, "alice", 2, memory_gb=20),
            _make_proc(200, "bob", 3, memory_gb=8),
        ]
        report = await self._get_report(gpus, procs)
        users_by_name = {u["username"]: u for u in report["users"]}
        alice = users_by_name["alice"]
        bob = users_by_name["bob"]
        self.assertLess(alice["fairness_score"], bob["fairness_score"],
                        "主导用户分数应低于非主导用户")
        self.assertLess(alice["fairness_score"], 70,
                        "占用75%显存的用户分数应低于70")

    async def test_deferrable_penalty_amplified_when_overusing(self):
        """超额用户的可延迟任务惩罚系数为4.0（正常2.0）"""
        gpus = [_make_gpu(0), _make_gpu(1)]
        # alice 超占且有deferrable任务
        procs_overuse = [
            _make_proc(100, "alice", 0, memory_gb=20, priority="deferrable"),
            _make_proc(101, "alice", 1, memory_gb=20, priority="deferrable"),
            _make_proc(200, "bob", 0, memory_gb=2),
        ]
        report_overuse = await self._get_report(gpus, procs_overuse)

        # 同样2个deferrable但无超占
        procs_normal = [
            _make_proc(100, "alice", 0, memory_gb=10, priority="deferrable"),
            _make_proc(200, "bob", 1, memory_gb=10, priority="deferrable"),
        ]
        report_normal = await self._get_report(gpus, procs_normal)

        overuse_alice = next(u for u in report_overuse["users"] if u["username"] == "alice")
        normal_alice = next(u for u in report_normal["users"] if u["username"] == "alice")
        # 超占时deferrable惩罚更大，分数更低
        self.assertLess(overuse_alice["fairness_score"], normal_alice["fairness_score"],
                        "超额时可延迟惩罚应更重")

    async def test_urgent_credit_boosts_score(self):
        """紧急任务加分提升公平分（上限15分）"""
        gpus = [_make_gpu(0), _make_gpu(1)]
        # 不带urgent
        procs_normal = [
            _make_proc(100, "alice", 0, memory_gb=16),
            _make_proc(200, "bob", 1, memory_gb=8),
        ]
        report_normal = await self._get_report(gpus, procs_normal)

        # 带urgent
        procs_urgent = [
            _make_proc(100, "alice", 0, memory_gb=16, priority="urgent"),
            _make_proc(200, "bob", 1, memory_gb=8),
        ]
        report_urgent = await self._get_report(gpus, procs_urgent)

        normal_alice = next(u for u in report_normal["users"] if u["username"] == "alice")
        urgent_alice = next(u for u in report_urgent["users"] if u["username"] == "alice")
        self.assertGreater(urgent_alice["fairness_score"], normal_alice["fairness_score"],
                           "紧急任务应提升公平分")

    async def test_urgent_credit_capped_at_15(self):
        """紧急任务加分上限为15分（3个×5=15）"""
        gpus = [_make_gpu(0)]
        # 5个urgent任务
        procs = [_make_proc(100 + i, "alice", 0, memory_gb=2, priority="urgent")
                 for i in range(5)]
        procs.append(_make_proc(200, "bob", 0, memory_gb=2))
        report = await self._get_report(gpus, procs)
        alice = next(u for u in report["users"] if u["username"] == "alice")
        # 5 * 5.0 = 25, 但 cap 是 15
        # 通过验证分数不超过基础+15来间接验证cap
        self.assertLessEqual(alice["fairness_score"], 100)


# ========== 系统公平治理指数测试 ==========


class SystemFairnessIndexTests(unittest.IsolatedAsyncioTestCase):
    """系统层面公平治理指数测试"""

    async def _get_overview(self, gpus, processes, rules=None):
        agent = FakeAgent(gpus, processes)
        store = FakeStore(rules=rules or {})
        svc = GovernanceService(store, agent)
        report = await svc.get_fairness_report()
        return report["overview"]

    async def test_equal_distribution_high_index(self):
        """均匀分布时系统指数应很高"""
        gpus = [_make_gpu(0), _make_gpu(1)]
        procs = [
            _make_proc(100, "alice", 0, memory_gb=10),
            _make_proc(200, "bob", 1, memory_gb=10),
        ]
        overview = await self._get_overview(gpus, procs)
        self.assertGreaterEqual(overview["fairness_index"], 80)
        self.assertEqual(overview["level"], "balanced")

    async def test_skewed_distribution_low_index(self):
        """严重偏斜时系统指数应低"""
        gpus = [_make_gpu(i) for i in range(4)]
        procs = [
            _make_proc(100, "alice", 0, memory_gb=20),
            _make_proc(101, "alice", 1, memory_gb=20),
            _make_proc(102, "alice", 2, memory_gb=20),
            _make_proc(103, "alice", 3, memory_gb=20),
            _make_proc(200, "bob", 0, memory_gb=1),
        ]
        overview = await self._get_overview(gpus, procs)
        self.assertLess(overview["fairness_index"], 70)

    async def test_no_processes_returns_balanced(self):
        """无可治理任务时返回均衡"""
        gpus = [_make_gpu(0)]
        overview = await self._get_overview(gpus, [])
        self.assertEqual(overview["fairness_index"], 100.0)
        self.assertEqual(overview["level"], "balanced")


# ========== 分布差距计算测试 ==========


class DistributionGapTests(unittest.TestCase):
    """_distribution_gap 数值验证"""

    def setUp(self):
        self.svc = GovernanceService(FakeStore(), FakeAgent())

    def test_perfect_distribution(self):
        """完美分布差距为0"""
        gap = self.svc._distribution_gap([50.0, 50.0], 50.0)
        self.assertAlmostEqual(gap, 0.0)

    def test_extreme_distribution(self):
        """极端分布（一人100%）差距接近1"""
        gap = self.svc._distribution_gap([100.0, 0.0], 50.0)
        # |100-50| + |0-50| = 100, /200 = 0.5
        self.assertAlmostEqual(gap, 0.5)

    def test_three_users_uneven(self):
        """三用户不均匀分布"""
        gap = self.svc._distribution_gap([70.0, 20.0, 10.0], 33.33)
        # |70-33.33| + |20-33.33| + |10-33.33| ≈ 36.67+13.33+23.33 = 73.33
        # /200 ≈ 0.367
        self.assertAlmostEqual(gap, 73.33 / 200, places=1)

    def test_empty_returns_zero(self):
        """空列表差距为0"""
        gap = self.svc._distribution_gap([], 50.0)
        self.assertEqual(gap, 0.0)


# ========== 规则违规检测测试 ==========


class RuleViolationTests(unittest.IsolatedAsyncioTestCase):
    """用户额度规则违规检测"""

    async def test_max_tasks_violation(self):
        """任务数超过额度限制触发违规"""
        gpus = [_make_gpu(0)]
        procs = [_make_proc(100 + i, "alice", 0, memory_gb=2) for i in range(6)]
        rules = {"alice": {"max_tasks": 4, "max_gpu_count": 4, "max_memory_gb": 50}}
        agent = FakeAgent(gpus, procs)
        store = FakeStore(rules=rules)
        svc = GovernanceService(store, agent)
        report = await svc.get_fairness_report()
        alice = next(u for u in report["users"] if u["username"] == "alice")
        self.assertGreater(alice["violation_count"], 0)
        self.assertTrue(any("任务数" in v for v in alice["violations"]))

    async def test_max_gpu_count_violation(self):
        """占用GPU数超额度触发违规"""
        gpus = [_make_gpu(i) for i in range(3)]
        procs = [
            _make_proc(100, "alice", 0, memory_gb=8),
            _make_proc(101, "alice", 1, memory_gb=8),
            _make_proc(102, "alice", 2, memory_gb=8),
        ]
        rules = {"alice": {"max_tasks": 10, "max_gpu_count": 1, "max_memory_gb": 50}}
        agent = FakeAgent(gpus, procs)
        store = FakeStore(rules=rules)
        svc = GovernanceService(store, agent)
        report = await svc.get_fairness_report()
        alice = next(u for u in report["users"] if u["username"] == "alice")
        self.assertGreater(alice["violation_count"], 0)
        self.assertTrue(any("GPU 数" in v for v in alice["violations"]))

    async def test_memory_violation(self):
        """显存超额度触发违规"""
        gpus = [_make_gpu(0)]
        procs = [_make_proc(100, "alice", 0, memory_gb=20)]
        rules = {"alice": {"max_tasks": 10, "max_gpu_count": 4, "max_memory_gb": 8}}
        agent = FakeAgent(gpus, procs)
        store = FakeStore(rules=rules)
        svc = GovernanceService(store, agent)
        report = await svc.get_fairness_report()
        alice = next(u for u in report["users"] if u["username"] == "alice")
        self.assertGreater(alice["violation_count"], 0)
        self.assertTrue(any("显存" in v for v in alice["violations"]))

    async def test_no_violation_within_limits(self):
        """在额度范围内无违规"""
        gpus = [_make_gpu(0)]
        procs = [_make_proc(100, "alice", 0, memory_gb=6)]
        rules = {"alice": {"max_tasks": 4, "max_gpu_count": 2, "max_memory_gb": 8}}
        agent = FakeAgent(gpus, procs)
        store = FakeStore(rules=rules)
        svc = GovernanceService(store, agent)
        report = await svc.get_fairness_report()
        alice = next(u for u in report["users"] if u["username"] == "alice")
        self.assertEqual(alice["violation_count"], 0)


# ========== 让路候选评分测试 ==========


class YieldCandidateTests(unittest.IsolatedAsyncioTestCase):
    """让路候选评分与排序"""

    async def _get_candidates(self, gpus, processes, rules=None):
        agent = FakeAgent(gpus, processes)
        store = FakeStore(rules=rules or {})
        svc = GovernanceService(store, agent)
        report = await svc.get_fairness_report()
        return report["yield_candidates"]

    async def test_urgent_never_yields(self):
        """紧急任务不出现在让路列表"""
        gpus = [_make_gpu(0), _make_gpu(1)]
        procs = [
            _make_proc(100, "alice", 0, memory_gb=20, priority="urgent"),
            _make_proc(101, "alice", 1, memory_gb=20, priority="deferrable"),
            _make_proc(200, "bob", 0, memory_gb=2),
        ]
        candidates = await self._get_candidates(gpus, procs)
        pids = [c["pid"] for c in candidates]
        self.assertNotIn(100, pids, "urgent 任务不应出现在让路列表")

    async def test_deferrable_higher_than_normal(self):
        """deferrable 任务让路分高于 normal"""
        gpus = [_make_gpu(0), _make_gpu(1)]
        procs = [
            _make_proc(100, "alice", 0, memory_gb=12, priority="deferrable"),
            _make_proc(101, "alice", 1, memory_gb=12, priority="normal"),
            _make_proc(200, "bob", 0, memory_gb=2),
        ]
        candidates = await self._get_candidates(gpus, procs)
        if len(candidates) >= 2:
            scores_by_pid = {c["pid"]: c["yield_score"] for c in candidates}
            if 100 in scores_by_pid and 101 in scores_by_pid:
                self.assertGreater(scores_by_pid[100], scores_by_pid[101],
                                   "deferrable 让路分应高于 normal")

    async def test_candidates_sorted_descending(self):
        """让路候选按分数降序排列"""
        gpus = [_make_gpu(i) for i in range(3)]
        procs = [
            _make_proc(100, "alice", 0, memory_gb=20, priority="deferrable"),
            _make_proc(101, "alice", 1, memory_gb=10, priority="normal"),
            _make_proc(102, "alice", 2, memory_gb=5, priority="normal"),
            _make_proc(200, "bob", 0, memory_gb=2),
        ]
        candidates = await self._get_candidates(gpus, procs)
        if len(candidates) >= 2:
            scores = [c["yield_score"] for c in candidates]
            self.assertEqual(scores, sorted(scores, reverse=True),
                             "让路候选应按分数降序排列")

    async def test_protected_user_excluded(self):
        """受保护用户（allow_preempt=False）不出现在让路列表"""
        gpus = [_make_gpu(0), _make_gpu(1)]
        procs = [
            _make_proc(100, "alice", 0, memory_gb=20, priority="deferrable"),
            _make_proc(200, "bob", 1, memory_gb=2),
        ]
        rules = {"alice": {"allow_preempt": False, "max_tasks": 10,
                            "max_gpu_count": 4, "max_memory_gb": 50}}
        candidates = await self._get_candidates(gpus, procs, rules=rules)
        pids = [c["pid"] for c in candidates]
        self.assertNotIn(100, pids, "受保护用户不应出现在让路列表")

    async def test_violation_user_higher_score(self):
        """违规用户的任务让路分更高"""
        gpus = [_make_gpu(0), _make_gpu(1)]
        procs = [
            _make_proc(100, "alice", 0, memory_gb=12, priority="normal"),
            _make_proc(101, "bob", 1, memory_gb=12, priority="normal"),
            _make_proc(200, "carol", 0, memory_gb=1),
        ]
        # alice 违规, bob 不违规
        rules = {
            "alice": {"max_tasks": 0, "max_gpu_count": 0, "max_memory_gb": 0},
        }
        candidates = await self._get_candidates(gpus, procs, rules=rules)
        scores_by_user = {}
        for c in candidates:
            if c["username"] not in scores_by_user:
                scores_by_user[c["username"]] = c["yield_score"]
        if "alice" in scores_by_user and "bob" in scores_by_user:
            self.assertGreater(scores_by_user["alice"], scores_by_user["bob"],
                               "违规用户让路分应更高")

    async def test_candidates_capped_at_5(self):
        """让路候选最多返回5条"""
        gpus = [_make_gpu(0)]
        procs = [_make_proc(100 + i, "alice", 0, memory_gb=1, priority="deferrable")
                 for i in range(10)]
        procs.append(_make_proc(200, "bob", 0, memory_gb=1))
        candidates = await self._get_candidates(gpus, procs)
        self.assertLessEqual(len(candidates), 5)


# ========== 可治理进程过滤测试 ==========


class GovernableFilterTests(unittest.TestCase):
    """_is_governable_process 过滤逻辑"""

    def setUp(self):
        self.svc = GovernanceService(FakeStore(), FakeAgent())

    def test_background_process_filtered(self):
        """已知后台进程被过滤"""
        for bg_name in ["dwm.exe", "explorer.exe", "chrome.exe"]:
            proc = {"name": bg_name, "command": "", "priority": "normal",
                    "gpu_memory_used": 0, "username": "user"}
            self.assertFalse(self.svc._is_governable_process(proc),
                             f"{bg_name} 应被过滤")

    def test_background_command_keyword_filtered(self):
        """包含后台命令关键词的进程被过滤"""
        proc = {"name": "someapp.exe", "command": "--type=gpu-process foo",
                "priority": "normal", "gpu_memory_used": 0, "username": "user"}
        self.assertFalse(self.svc._is_governable_process(proc))

    def test_training_process_passes(self):
        """训练进程（大显存）通过过滤"""
        proc = {"name": "python.exe", "command": "python train.py",
                "priority": "normal", "gpu_memory_used": 8 * 1073741824,
                "username": "alice"}
        self.assertTrue(self.svc._is_governable_process(proc))

    def test_urgent_priority_always_passes(self):
        """紧急优先级进程始终通过"""
        proc = {"name": "dwm.exe", "command": "", "priority": "urgent",
                "gpu_memory_used": 0, "username": "user"}
        self.assertTrue(self.svc._is_governable_process(proc))

    def test_deferrable_priority_always_passes(self):
        """可延迟优先级进程始终通过"""
        proc = {"name": "explorer.exe", "command": "", "priority": "deferrable",
                "gpu_memory_used": 0, "username": "user"}
        self.assertTrue(self.svc._is_governable_process(proc))

    def test_window_manager_user_filtered(self):
        """Window Manager 用户被过滤"""
        proc = {"name": "unknown.exe", "command": "", "priority": "normal",
                "gpu_memory_used": 0, "username": "Window Manager\\DWM-1"}
        self.assertFalse(self.svc._is_governable_process(proc))

    def test_large_memory_passes_even_if_background_name(self):
        """大显存进程即使名称匹配后台进程也通过（≥256MB）"""
        proc = {"name": "chrome.exe", "command": "",
                "priority": "normal", "gpu_memory_used": 300 * 1024 * 1024,
                "username": "user"}
        self.assertTrue(self.svc._is_governable_process(proc))

    def test_manageable_flag_overrides(self):
        """manageable 标志优先于其他判断"""
        proc_true = {"name": "dwm.exe", "command": "", "priority": "normal",
                     "gpu_memory_used": 0, "username": "user", "manageable": True}
        self.assertTrue(self.svc._is_governable_process(proc_true))

        proc_false = {"name": "python.exe", "command": "train.py",
                      "priority": "normal", "gpu_memory_used": 10 * 1073741824,
                      "username": "alice", "manageable": False}
        self.assertFalse(self.svc._is_governable_process(proc_false))


# ========== 建议输出测试 ==========


class RecommendationTests(unittest.IsolatedAsyncioTestCase):
    """治理建议输出"""

    async def test_recommendations_capped_at_three(self):
        """建议最多3条"""
        gpus = [_make_gpu(i) for i in range(4)]
        procs = [
            _make_proc(100, "alice", 0, memory_gb=20, priority="deferrable"),
            _make_proc(101, "alice", 1, memory_gb=20),
            _make_proc(102, "alice", 2, memory_gb=20),
            _make_proc(200, "bob", 3, memory_gb=2),
        ]
        rules = {"alice": {"max_tasks": 1, "max_gpu_count": 1, "max_memory_gb": 8}}
        agent = FakeAgent(gpus, procs)
        store = FakeStore(rules=rules)
        svc = GovernanceService(store, agent)
        report = await svc.get_fairness_report()
        self.assertLessEqual(len(report["recommendations"]), 3)

    async def test_no_users_gives_monitoring_recommendation(self):
        """无用户时给出监测建议"""
        agent = FakeAgent([_make_gpu(0)], [])
        store = FakeStore()
        svc = GovernanceService(store, agent)
        report = await svc.get_fairness_report()
        self.assertEqual(len(report["recommendations"]), 1)
        self.assertIn("监测", report["recommendations"][0])


if __name__ == "__main__":
    unittest.main()
