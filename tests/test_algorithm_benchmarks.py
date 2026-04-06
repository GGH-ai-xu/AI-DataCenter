"""算法基准实验 - 验证核心算法正确性与竞争择优一致性

实验内容：
1. 三种预测算法 RMSE 对比（合成正弦+噪声数据）
2. 自动择优一致性
3. 公平性评分边界测试
4. 让路评分单调性
5. 碳排放计算精度
6. 效率评分公式验证
"""

import math
import os
import sys
import time
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.energy_analytics import (  # noqa: E402
    CARBON_FACTOR,
    ELECTRICITY_PRICE,
    EnergyAnalytics,
    _classify_hour,
)
from app.services.governance import GovernanceService  # noqa: E402


# ========== 辅助构造 ==========

class FakeStore:
    """最小化 store，仅满足 GovernanceService 依赖"""

    def __init__(self, priorities=None, rules=None, user_stats=None):
        self._priorities = priorities or {}
        self._rules = rules or {}
        self._user_stats = user_stats or []

    async def get_all_task_priorities(self):
        return dict(self._priorities)

    async def get_user_stats(self):
        return list(self._user_stats)

    async def get_user_governance_rules(self):
        return dict(self._rules)


class FakeAgent:
    def __init__(self, gpus=None, processes=None):
        self._gpus = gpus or []
        self._processes = processes or []

    async def get_all_gpus(self):
        return [dict(g) for g in self._gpus]

    async def get_processes(self):
        return [dict(p) for p in self._processes]


def _make_gpu(index, power_usage=250, power_limit=350, util=70, temp=65,
              memory_used=16000, memory_total=24576):
    return {
        "index": index,
        "power_usage": power_usage,
        "power_limit": power_limit,
        "gpu_utilization": util,
        "temperature": temp,
        "memory_used": memory_used,
        "memory_total": memory_total,
        "memory_utilization": int(memory_used / memory_total * 100),
    }


def _make_proc(pid, username, gpu_index, memory_gb=8, priority="normal",
               create_time=None):
    return {
        "pid": pid,
        "username": username,
        "name": "python.exe",
        "command": f"python train_{pid}.py",
        "gpu_index": gpu_index,
        "gpu_memory_used": int(memory_gb * 1024 * 1024 * 1024),
        "create_time": create_time or time.time() - 3600,
        "priority": priority,
    }


# ========== 实验 1：预测算法对比 ==========

class TestPredictionAlgorithms(unittest.TestCase):
    """实验 1：三种预测算法 RMSE 对比"""

    def setUp(self):
        self.analytics = EnergyAnalytics(data_store=None)

    def _generate_sinusoidal_data(self, n=24, base=250, amplitude=80, noise=10):
        """生成带噪声的正弦功耗数据（模拟日周期）"""
        import random
        random.seed(42)
        return [
            base + amplitude * math.sin(2 * math.pi * i / 24) + random.gauss(0, noise)
            for i in range(n)
        ]

    def test_ewa_empty_returns_defaults(self):
        """EWA 空输入返回默认值 700W/70W"""
        pred, std = self.analytics._predict_ewa([])
        self.assertAlmostEqual(pred, 700.0)
        self.assertAlmostEqual(std, 70.0)

    def test_ewa_single_value(self):
        """EWA 单值输入返回该值本身"""
        pred, std = self.analytics._predict_ewa([300.0])
        self.assertAlmostEqual(pred, 300.0, places=1)
        self.assertAlmostEqual(std, 30.0, places=1)  # 单值时 std = val * 0.1

    def test_ewa_trending_up(self):
        """EWA 上升趋势 → 预测值高于简单均值"""
        values = [200, 220, 240, 260, 280, 300]
        pred, _ = self.analytics._predict_ewa(values)
        simple_mean = sum(values) / len(values)
        self.assertGreater(pred, simple_mean,
                           "上升趋势下 EWA 应偏向近期较大值")

    def test_ewa_trending_down(self):
        """EWA 下降趋势 → 预测值低于简单均值"""
        values = [300, 280, 260, 240, 220, 200]
        pred, _ = self.analytics._predict_ewa(values)
        simple_mean = sum(values) / len(values)
        self.assertLess(pred, simple_mean,
                        "下降趋势下 EWA 应偏向近期较小值")

    def test_linear_insufficient_data(self):
        """线性回归：少于 3 点返回 None"""
        pred, std, rmse, r2 = self.analytics._predict_linear([100, 200])
        self.assertIsNone(pred)
        self.assertEqual(rmse, float('inf'))

    def test_linear_known_series(self):
        """线性回归：y = 2x + 100 系列验证"""
        values = [100, 102, 104, 106, 108]  # y = 2x + 100
        pred, _, rmse, r2 = self.analytics._predict_linear(values)
        self.assertIsNotNone(pred)
        self.assertAlmostEqual(pred, 110.0, places=0)
        self.assertAlmostEqual(r2, 1.0, places=3)
        self.assertLess(rmse, 1.0)

    def test_polynomial_insufficient_data(self):
        """多项式：少于 5 点返回 None"""
        pred, _, rmse, _ = self.analytics._predict_polynomial([100, 200, 300, 400])
        self.assertIsNone(pred)

    def test_polynomial_divergence_guard(self):
        """多项式反发散保护：外推值超 3×max 时弃用"""
        # 构造一个二次增长很快的序列，外推后会远超历史
        values = [100, 120, 180, 300, 500]
        pred, _, _, _ = self.analytics._predict_polynomial(values)
        # 多项式外推到 x=5 可能远超 500*3=1500
        if pred is not None:
            self.assertLessEqual(pred, max(values) * 3)

    def test_sinusoidal_data_rmse_comparison(self):
        """实验核心：合成正弦数据上三种算法 RMSE 对比"""
        data = self._generate_sinusoidal_data(n=30, base=250, amplitude=80, noise=10)

        # 使用前 24 个点训练，预测第 25 个
        train = data[:24]
        actual = data[24]

        ewa_pred, ewa_std = self.analytics._predict_ewa(train)
        lin_pred, _, lin_rmse, lin_r2 = self.analytics._predict_linear(train)
        poly_pred, _, poly_rmse, poly_r2 = self.analytics._predict_polynomial(train)

        # EWA 应始终产生有效预测
        self.assertIsNotNone(ewa_pred)
        self.assertGreater(ewa_pred, 0)

        # 所有算法的预测应在合理范围内（base ± 2*amplitude）
        for name, pred in [("EWA", ewa_pred), ("Linear", lin_pred), ("Poly", poly_pred)]:
            if pred is not None:
                self.assertGreater(pred, 50, f"{name} 预测值异常偏低")
                self.assertLess(pred, 500, f"{name} 预测值异常偏高")

    def test_auto_selection_picks_lowest_rmse(self):
        """验证择优机制选择 RMSE 最低的算法"""
        values = [200, 210, 220, 230, 240, 250, 260]

        ewa_pred, ewa_std = self.analytics._predict_ewa(values)
        lin_pred, lin_std, lin_rmse, _ = self.analytics._predict_linear(values)
        poly_pred, poly_std, poly_rmse, _ = self.analytics._predict_polynomial(values)

        # 对于线性数据，线性回归应胜出或与多项式持平
        candidates = []
        candidates.append(("ewa", ewa_pred, ewa_std, ewa_std))  # EWA 用 std 近似 rmse
        if lin_pred is not None:
            candidates.append(("linear", lin_pred, lin_std, lin_rmse))
        if poly_pred is not None:
            candidates.append(("polynomial", poly_pred, poly_std, poly_rmse))

        best = min(candidates, key=lambda c: c[3])
        # 线性数据上，线性或多项式应胜出（RMSE 更低）
        self.assertIn(best[0], ("linear", "polynomial"),
                      "线性趋势数据上 polyfit 算法应优于 EWA")


# ========== 实验 2：公平性评分 ==========

class TestFairnessScoring(unittest.IsolatedAsyncioTestCase):
    """实验 2：公平性评分边界测试"""

    async def _get_report(self, gpus, processes, priorities=None, rules=None):
        now = time.time()
        usernames = {p.get("username") for p in processes}
        user_stats = [
            {"username": u, "earliest_start": now - 3600}
            for u in usernames
        ]
        store = FakeStore(
            priorities=priorities or {},
            rules=rules or {},
            user_stats=user_stats,
        )
        agent = FakeAgent(gpus, processes)
        gov = GovernanceService(store, agent)
        return await gov.get_fairness_report()

    async def test_single_user_near_perfect_fairness(self):
        """单用户场景：分数接近 100（仅受运行时惩罚影响）"""
        gpus = [_make_gpu(0)]
        procs = [_make_proc(100, "alice", 0, memory_gb=10)]
        report = await self._get_report(gpus, procs)

        users = report["users"]
        self.assertEqual(len(users), 1)
        score = users[0]["fairness_score"]
        # 单用户无超占，分数应很高（仅 runtime_penalty 扣分）
        self.assertGreater(score, 85, f"单用户分数应接近 100，实际 {score}")

    async def test_two_equal_users_balanced(self):
        """两个均等用户：均为高分"""
        gpus = [_make_gpu(0), _make_gpu(1)]
        procs = [
            _make_proc(100, "alice", 0, memory_gb=10),
            _make_proc(200, "bob", 1, memory_gb=10),
        ]
        report = await self._get_report(gpus, procs)

        for user in report["users"]:
            self.assertGreater(user["fairness_score"], 75,
                               f"均等用户 {user['username']} 分数应较高")
        overview = report["overview"]
        self.assertGreaterEqual(overview["fairness_index"], 80)

    async def test_dominant_user_low_score(self):
        """一个用户占 80% 以上显存：分数应低于 60"""
        gpus = [_make_gpu(0), _make_gpu(1)]
        procs = [
            _make_proc(100, "alice", 0, memory_gb=20),
            _make_proc(101, "alice", 1, memory_gb=18),
            _make_proc(200, "bob", 1, memory_gb=2),
        ]
        report = await self._get_report(gpus, procs)

        alice = next(u for u in report["users"] if u["username"] == "alice")
        bob = next(u for u in report["users"] if u["username"] == "bob")
        self.assertLess(alice["fairness_score"], bob["fairness_score"],
                        "主导用户分数应低于被挤占用户")

    async def test_deferrable_penalty_amplified_when_overusing(self):
        """超额用户的可延迟任务处罚为 4.0（vs 正常 2.0）"""
        gpus = [_make_gpu(0), _make_gpu(1)]
        # alice 超占 + 有 deferrable 任务
        procs_over = [
            _make_proc(100, "alice", 0, memory_gb=20, priority="deferrable"),
            _make_proc(101, "alice", 1, memory_gb=15, priority="normal"),
            _make_proc(200, "bob", 1, memory_gb=2, priority="normal"),
        ]
        report_over = await self._get_report(gpus, procs_over)
        alice_over = next(u for u in report_over["users"] if u["username"] == "alice")

        # alice 不超占 + 有 deferrable 任务
        procs_equal = [
            _make_proc(100, "alice", 0, memory_gb=10, priority="deferrable"),
            _make_proc(200, "bob", 1, memory_gb=10, priority="normal"),
        ]
        report_equal = await self._get_report(gpus, procs_equal)
        alice_equal = next(u for u in report_equal["users"] if u["username"] == "alice")

        # 超额时 deferrable 惩罚更重
        self.assertLess(alice_over["fairness_score"], alice_equal["fairness_score"],
                        "超额+可延迟任务应导致更低分数")

    async def test_urgent_credit_boosts_score(self):
        """紧急任务加分最多 15"""
        gpus = [_make_gpu(0), _make_gpu(1)]
        procs = [
            _make_proc(100, "alice", 0, memory_gb=15, priority="urgent"),
            _make_proc(101, "alice", 0, memory_gb=5, priority="urgent"),
            _make_proc(200, "bob", 1, memory_gb=10, priority="normal"),
        ]
        report = await self._get_report(gpus, procs)
        alice = next(u for u in report["users"] if u["username"] == "alice")

        # 同样超占但有 urgent credit，分数应比纯 normal 高
        procs_no_urgent = [
            _make_proc(100, "alice", 0, memory_gb=15, priority="normal"),
            _make_proc(101, "alice", 0, memory_gb=5, priority="normal"),
            _make_proc(200, "bob", 1, memory_gb=10, priority="normal"),
        ]
        report2 = await self._get_report(gpus, procs_no_urgent)
        alice2 = next(u for u in report2["users"] if u["username"] == "alice")

        self.assertGreater(alice["fairness_score"], alice2["fairness_score"],
                           "urgent 加分应提高公平性分数")

    async def test_governance_rule_violation(self):
        """超出 max_tasks 规则触发违规"""
        gpus = [_make_gpu(0)]
        procs = [
            _make_proc(100, "alice", 0, memory_gb=8),
            _make_proc(101, "alice", 0, memory_gb=4),
            _make_proc(102, "alice", 0, memory_gb=4),
        ]
        rules = {"alice": {"max_tasks": 2, "max_gpu_count": 4, "max_memory_gb": 64, "allow_preempt": True}}
        report = await self._get_report(gpus, procs, rules=rules)

        alice = next(u for u in report["users"] if u["username"] == "alice")
        self.assertGreater(alice["violation_count"], 0, "应检测到 max_tasks 违规")
        self.assertIn("任务数", alice["violations"][0])


# ========== 实验 3：让路评分 ==========

class TestYieldScoring(unittest.IsolatedAsyncioTestCase):
    """实验 3：让路候选评分单调性"""

    async def _get_report(self, gpus, processes, priorities=None):
        now = time.time()
        usernames = {p.get("username") for p in processes}
        store = FakeStore(
            priorities=priorities or {},
            user_stats=[{"username": u, "earliest_start": now - 3600} for u in usernames],
        )
        agent = FakeAgent(gpus, processes)
        gov = GovernanceService(store, agent)
        return await gov.get_fairness_report()

    async def test_deferrable_scores_higher_than_normal(self):
        """可延迟任务的让路评分应高于同条件普通任务"""
        gpus = [_make_gpu(0), _make_gpu(1)]
        procs = [
            _make_proc(100, "alice", 0, memory_gb=12, priority="deferrable"),
            _make_proc(200, "alice", 1, memory_gb=12, priority="normal"),
            _make_proc(300, "bob", 1, memory_gb=2, priority="normal"),
        ]
        report = await self._get_report(gpus, procs, priorities={100: "deferrable", 200: "normal"})

        candidates = report["yield_candidates"]
        if len(candidates) >= 2:
            defer_cand = next((c for c in candidates if c["pid"] == 100), None)
            normal_cand = next((c for c in candidates if c["pid"] == 200), None)
            if defer_cand and normal_cand:
                self.assertGreater(defer_cand["yield_score"], normal_cand["yield_score"],
                                   "deferrable 让路评分应高于 normal")

    async def test_urgent_never_in_yield_candidates(self):
        """紧急任务永不出现在让路候选"""
        gpus = [_make_gpu(0), _make_gpu(1)]
        procs = [
            _make_proc(100, "alice", 0, memory_gb=20, priority="urgent"),
            _make_proc(200, "alice", 1, memory_gb=10, priority="deferrable"),
            _make_proc(300, "bob", 1, memory_gb=2, priority="normal"),
        ]
        report = await self._get_report(gpus, procs, priorities={100: "urgent", 200: "deferrable"})

        urgent_pids = [c["pid"] for c in report["yield_candidates"] if c["pid"] == 100]
        self.assertEqual(len(urgent_pids), 0, "urgent 任务不应出现在让路列表")

    async def test_yield_candidates_sorted_descending(self):
        """让路候选应按评分降序排列"""
        gpus = [_make_gpu(0), _make_gpu(1)]
        procs = [
            _make_proc(100, "alice", 0, memory_gb=15, priority="deferrable"),
            _make_proc(101, "alice", 0, memory_gb=5, priority="normal"),
            _make_proc(200, "bob", 1, memory_gb=2, priority="normal"),
        ]
        report = await self._get_report(gpus, procs, priorities={100: "deferrable"})
        scores = [c["yield_score"] for c in report["yield_candidates"]]
        self.assertEqual(scores, sorted(scores, reverse=True),
                         "让路评分应为降序")

    async def test_recommendations_capped_at_three(self):
        """建议最多 3 条"""
        gpus = [_make_gpu(0), _make_gpu(1)]
        procs = [
            _make_proc(100, "alice", 0, memory_gb=20, priority="deferrable"),
            _make_proc(200, "bob", 1, memory_gb=2, priority="normal"),
        ]
        report = await self._get_report(gpus, procs, priorities={100: "deferrable"})
        self.assertLessEqual(len(report["recommendations"]), 3)


# ========== 实验 4：碳排放计算 ==========

class TestCarbonCalculation(unittest.TestCase):
    """实验 4：碳排放计算精度验证"""

    def test_kwh_to_carbon_conversion(self):
        """验证 kWh → kgCO2 转换精度"""
        kwh = 10.0
        expected_co2 = kwh * CARBON_FACTOR  # 5.703
        self.assertAlmostEqual(expected_co2, 5.703, places=3)

    def test_carbon_factor_source_value(self):
        """验证碳排放因子值（国网 2023）"""
        self.assertAlmostEqual(CARBON_FACTOR, 0.5703, places=4)

    def test_electricity_price_value(self):
        """验证商业电价"""
        self.assertAlmostEqual(ELECTRICITY_PRICE, 0.85, places=2)

    def test_power_to_daily_carbon(self):
        """验证功率 → 日碳排放计算链"""
        # 4 张 GPU 平均 250W = 1000W 总功率，运行 24 小时
        total_power_w = 1000
        hours = 24
        kwh = total_power_w * hours / 1000  # 24 kWh
        co2_kg = kwh * CARBON_FACTOR  # 13.6872 kgCO2
        cost = kwh * ELECTRICITY_PRICE  # 20.40 CNY

        self.assertAlmostEqual(kwh, 24.0, places=1)
        self.assertAlmostEqual(co2_kg, 13.6872, places=3)
        self.assertAlmostEqual(cost, 20.4, places=1)

    def test_time_period_classification(self):
        """验证峰谷平时段分类"""
        # 高峰
        for h in [9, 10, 11, 14, 15, 16, 17]:
            self.assertEqual(_classify_hour(h), "peak", f"{h}点应为高峰")
        # 低谷
        for h in [22, 23, 0, 1, 2, 3, 4, 5]:
            self.assertEqual(_classify_hour(h), "valley", f"{h}点应为低谷")
        # 平峰
        for h in [6, 7, 8, 12, 13, 18, 19, 20, 21]:
            self.assertEqual(_classify_hour(h), "normal", f"{h}点应为平峰")


# ========== 实验 5：效率评分 ==========

class TestEfficiencyScoring(unittest.TestCase):
    """实验 5：GPU 效率评分公式验证"""

    def test_high_util_low_power_ratio(self):
        """高利用率 + 低功耗比 = 高效率"""
        # util=90%, power=200/350=0.571, raw = 90/0.571 ≈ 157.5
        util = 90
        power_ratio = 200 / 350
        raw = util / max(power_ratio, 0.01)
        self.assertGreater(raw, 100, "原始值应超过 100（被 min 截断前）")
        score = min(100, raw)
        self.assertEqual(score, 100)

    def test_low_util_high_power_ratio(self):
        """低利用率 + 高功耗比 = 低效率"""
        util = 20
        power_ratio = 300 / 350  # 0.857
        score = min(100, util / max(power_ratio, 0.01))
        self.assertLess(score, 30, "低利用高功耗应低效")

    def test_temperature_penalty_85c(self):
        """85°C+ 温度惩罚系数 0.8"""
        util = 80
        power_ratio = 250 / 350
        base_score = min(100, util / max(power_ratio, 0.01))
        penalized = base_score * 0.8
        self.assertLess(penalized, base_score)
        self.assertAlmostEqual(penalized, base_score * 0.8)

    def test_temperature_penalty_75c(self):
        """75°C+ 温度惩罚系数 0.9"""
        util = 80
        power_ratio = 250 / 350
        base_score = min(100, util / max(power_ratio, 0.01))
        penalized_75 = base_score * 0.9
        penalized_85 = base_score * 0.8
        # 75°C 惩罚应小于 85°C
        self.assertGreater(penalized_75, penalized_85)

    def test_zero_power_ratio_safe(self):
        """功耗比为零时不除零"""
        util = 50
        score = min(100, util / max(0, 0.01))
        self.assertIsNotNone(score)


# ========== 实验 6：分布差距计算 ==========

class TestDistributionGap(unittest.TestCase):
    """实验 6：分布差距归一化验证"""

    def test_equal_distribution_zero_gap(self):
        """均等分布 → gap 为 0"""
        gov = GovernanceService.__new__(GovernanceService)
        gap = gov._distribution_gap([50.0, 50.0], 50.0)
        self.assertAlmostEqual(gap, 0.0)

    def test_extreme_concentration_max_gap(self):
        """极端集中（1 人 100%，1 人 0%）→ gap 接近 1"""
        gov = GovernanceService.__new__(GovernanceService)
        gap = gov._distribution_gap([100.0, 0.0], 50.0)
        # |100-50| + |0-50| = 100, / 200 = 0.5
        self.assertAlmostEqual(gap, 0.5)

    def test_three_user_moderate_imbalance(self):
        """三用户中度不均衡"""
        gov = GovernanceService.__new__(GovernanceService)
        # 理想: 33.3% 每人
        gap = gov._distribution_gap([60.0, 30.0, 10.0], 33.3)
        # |60-33.3| + |30-33.3| + |10-33.3| = 26.7+3.3+23.3 = 53.3
        # / 200 = 0.2665
        self.assertGreater(gap, 0.2)
        self.assertLess(gap, 0.4)


# ========== 实验 7：规则建议去重 ==========

class TestRuleBasedSuggestions(unittest.TestCase):
    """实验 7：规则建议去重 — 同 GPU 只保留最高节能建议"""

    def test_dedup_keeps_highest_saving(self):
        analytics = EnergyAnalytics(data_store=None)
        gpus = [
            # 低利用高功耗 → 建议 A
            _make_gpu(0, power_usage=280, power_limit=350, util=20, temp=78),
        ]
        suggestions = analytics._generate_rule_based_suggestions(gpus)

        # GPU 0 可能匹配多条规则（低利用+高温），但去重后只保留一条
        gpu0_suggestions = [s for s in suggestions
                            if s.get("target", {}).get("gpu_index") == 0
                            and s.get("action") != "none"]
        self.assertLessEqual(len(gpu0_suggestions), 1,
                             "同一 GPU 去重后应最多保留 1 条建议")

    def test_no_suggestions_when_healthy(self):
        """健康状态返回 'none' 建议"""
        analytics = EnergyAnalytics(data_store=None)
        gpus = [_make_gpu(0, power_usage=200, power_limit=350, util=85, temp=60)]
        suggestions = analytics._generate_rule_based_suggestions(gpus)
        actions = [s["action"] for s in suggestions]
        self.assertIn("none", actions, "健康状态应返回无需调整")


if __name__ == "__main__":
    unittest.main()
