import math
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.energy_analytics import (  # noqa: E402
    CARBON_FACTOR,
    ELECTRICITY_PRICE,
    EnergyAnalytics,
    _classify_hour,
)

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# --------------- Fakes ---------------


class FakeStore:
    """最小化 store 用于直接算法测试"""

    def __init__(self, hourly_data=None, gpu_latest=None, power_summary=None):
        self._hourly = hourly_data or []
        self._latest = gpu_latest or []
        self._power_summary = power_summary or {}

    async def get_hourly_power_aggregation(self, hours=168):
        return self._hourly

    async def get_all_gpu_latest(self):
        return self._latest

    async def get_power_summary(self, hours):
        return self._power_summary or {
            "hours": hours, "gpus": [], "total_avg_power": 0,
        }

    async def save_optimization_snapshot(self, data):
        pass


class FakeAgent:
    def __init__(self, gpus=None, processes=None):
        self._gpus = gpus or []
        self._processes = processes or []

    async def get_all_gpus(self):
        return self._gpus

    async def get_processes(self):
        return self._processes


def _make_analytics(store=None, agent=None, llm=None):
    return EnergyAnalytics(
        data_store=store or FakeStore(),
        llm_service=llm,
        agent_client=agent,
    )


# ========== EWA 预测测试 ==========


class EWAPredictionTests(unittest.TestCase):
    """指数加权平均预测算法"""

    def setUp(self):
        self.analytics = _make_analytics()

    def test_empty_returns_defaults(self):
        """空数据返回默认值 700W / 70W"""
        pred, std = self.analytics._predict_ewa([])
        self.assertAlmostEqual(pred, 700.0)
        self.assertAlmostEqual(std, 70.0)

    def test_single_value(self):
        """单个值返回该值，std 为 10%"""
        pred, std = self.analytics._predict_ewa([200.0])
        self.assertAlmostEqual(pred, 200.0)
        self.assertAlmostEqual(std, 20.0)  # 200 * 0.1

    def test_trending_up(self):
        """上升趋势时预测值高于简单平均"""
        values = [100, 120, 140, 160, 180, 200]
        pred, _ = self.analytics._predict_ewa(values)
        simple_avg = sum(values) / len(values)
        self.assertGreater(pred, simple_avg,
                           "EWA 应偏向近期（更高的值）")

    def test_trending_down(self):
        """下降趋势时预测值低于简单平均"""
        values = [200, 180, 160, 140, 120, 100]
        pred, _ = self.analytics._predict_ewa(values)
        simple_avg = sum(values) / len(values)
        self.assertLess(pred, simple_avg,
                        "EWA 应偏向近期（更低的值）")

    def test_constant_series_zero_variance(self):
        """常数序列方差为 0"""
        pred, std = self.analytics._predict_ewa([250.0] * 10)
        self.assertAlmostEqual(pred, 250.0, places=1)
        self.assertAlmostEqual(std, 0.0, places=3)

    def test_alpha_weighting(self):
        """验证 α=0.3 使得近期值权重更高"""
        # 第一组: 旧高新低
        pred_old_high, _ = self.analytics._predict_ewa([300, 300, 300, 100, 100, 100])
        # 第二组: 旧低新高
        pred_old_low, _ = self.analytics._predict_ewa([100, 100, 100, 300, 300, 300])
        self.assertGreater(pred_old_low, pred_old_high,
                           "新高旧低的预测应大于新低旧高")


# ========== 线性回归预测测试 ==========


@unittest.skipUnless(HAS_NUMPY, "numpy not available")
class LinearPredictionTests(unittest.TestCase):
    """线性回归预测"""

    def setUp(self):
        self.analytics = _make_analytics()

    def test_insufficient_data_returns_none(self):
        """少于3个数据点返回 None"""
        pred, std, rmse, r2 = self.analytics._predict_linear([100, 200])
        self.assertIsNone(pred)

    def test_perfect_linear(self):
        """完美线性序列 y=2x+1"""
        values = [1.0, 3.0, 5.0, 7.0, 9.0]
        pred, std, rmse, r2 = self.analytics._predict_linear(values)
        self.assertAlmostEqual(pred, 11.0, places=1)
        self.assertAlmostEqual(r2, 1.0, places=3)
        self.assertAlmostEqual(rmse, 0.0, places=3)

    def test_noisy_linear_positive_r_squared(self):
        """含噪声线性数据 R² 仍应正"""
        values = [100, 115, 125, 145, 155, 170, 190]
        pred, std, rmse, r2 = self.analytics._predict_linear(values)
        self.assertIsNotNone(pred)
        self.assertGreater(r2, 0.9)
        self.assertGreater(pred, values[-1])

    def test_extrapolation_direction(self):
        """外推方向与趋势一致"""
        increasing = [100, 120, 140, 160]
        pred_up, _, _, _ = self.analytics._predict_linear(increasing)
        self.assertGreater(pred_up, 160)

        decreasing = [200, 180, 160, 140]
        pred_down, _, _, _ = self.analytics._predict_linear(decreasing)
        self.assertLess(pred_down, 140)


# ========== 多项式预测测试 ==========


@unittest.skipUnless(HAS_NUMPY, "numpy not available")
class PolynomialPredictionTests(unittest.TestCase):
    """二次多项式预测"""

    def setUp(self):
        self.analytics = _make_analytics()

    def test_insufficient_data_returns_none(self):
        """少于5个数据点返回 None"""
        pred, std, rmse, r2 = self.analytics._predict_polynomial([1, 2, 3, 4])
        self.assertIsNone(pred)

    def test_perfect_quadratic(self):
        """完美二次序列 y=x²"""
        values = [0, 1, 4, 9, 16, 25]
        pred, std, rmse, r2 = self.analytics._predict_polynomial(values)
        self.assertIsNotNone(pred)
        self.assertAlmostEqual(pred, 36.0, places=0)
        self.assertAlmostEqual(r2, 1.0, places=3)

    def test_divergence_guard_negative(self):
        """预测为负时返回 None（反发散保护）"""
        # 构造一个会外推到负值的序列
        values = [100, 80, 50, 20, 5]
        pred, std, rmse, r2 = self.analytics._predict_polynomial(values)
        # 二次下降趋势可能预测出负值
        if pred is not None:
            self.assertGreaterEqual(pred, 0, "通过反发散保护应返回None或非负")

    def test_divergence_guard_extreme(self):
        """预测超过 3*max 时返回 None（反发散保护）"""
        # 构造急速增长序列
        values = [10, 50, 200, 500, 900]
        pred, std, rmse, r2 = self.analytics._predict_polynomial(values)
        if pred is not None:
            self.assertLessEqual(pred, max(values) * 3,
                                 "反发散保护应拒绝超过3倍max的预测")


# ========== 效率评分测试 ==========


class EfficiencyScoreTests(unittest.IsolatedAsyncioTestCase):
    """GPU 效率评分公式"""

    async def test_high_util_high_efficiency(self):
        """高利用率+低功耗比=高效率"""
        gpus = [{
            "gpu_index": 0, "gpu_utilization": 90,
            "power_usage": 150, "power_limit": 350,
            "temperature": 65, "memory_used": 16000, "memory_total": 24576,
        }]
        store = FakeStore(gpu_latest=gpus)
        analytics = _make_analytics(store=store)
        results = await analytics.get_gpu_efficiency()
        self.assertGreater(results[0]["score"], 80)

    async def test_low_util_low_efficiency(self):
        """低利用率+高功耗比=低效率"""
        gpus = [{
            "gpu_index": 0, "gpu_utilization": 10,
            "power_usage": 300, "power_limit": 350,
            "temperature": 65, "memory_used": 16000, "memory_total": 24576,
        }]
        store = FakeStore(gpu_latest=gpus)
        analytics = _make_analytics(store=store)
        results = await analytics.get_gpu_efficiency()
        self.assertLess(results[0]["score"], 30)

    async def test_temperature_penalty_85c(self):
        """85°C+ 温度惩罚系数 0.8"""
        base_gpus = [{
            "gpu_index": 0, "gpu_utilization": 80,
            "power_usage": 250, "power_limit": 350,
            "temperature": 60, "memory_used": 16000, "memory_total": 24576,
        }]
        hot_gpus = [{
            "gpu_index": 0, "gpu_utilization": 80,
            "power_usage": 250, "power_limit": 350,
            "temperature": 88, "memory_used": 16000, "memory_total": 24576,
        }]
        normal_results = await _make_analytics(store=FakeStore(gpu_latest=base_gpus)).get_gpu_efficiency()
        hot_results = await _make_analytics(store=FakeStore(gpu_latest=hot_gpus)).get_gpu_efficiency()
        # 温度惩罚 0.8
        self.assertAlmostEqual(
            hot_results[0]["score"],
            normal_results[0]["score"] * 0.8,
            places=0,
        )

    async def test_temperature_penalty_75c(self):
        """75-84°C 温度惩罚系数 0.9"""
        base_gpus = [{
            "gpu_index": 0, "gpu_utilization": 80,
            "power_usage": 250, "power_limit": 350,
            "temperature": 60, "memory_used": 16000, "memory_total": 24576,
        }]
        warm_gpus = [{
            "gpu_index": 0, "gpu_utilization": 80,
            "power_usage": 250, "power_limit": 350,
            "temperature": 78, "memory_used": 16000, "memory_total": 24576,
        }]
        normal_results = await _make_analytics(store=FakeStore(gpu_latest=base_gpus)).get_gpu_efficiency()
        warm_results = await _make_analytics(store=FakeStore(gpu_latest=warm_gpus)).get_gpu_efficiency()
        self.assertAlmostEqual(
            warm_results[0]["score"],
            normal_results[0]["score"] * 0.9,
            places=0,
        )

    async def test_score_capped_at_100(self):
        """效率分上限100"""
        gpus = [{
            "gpu_index": 0, "gpu_utilization": 95,
            "power_usage": 50, "power_limit": 350,
            "temperature": 40, "memory_used": 16000, "memory_total": 24576,
        }]
        store = FakeStore(gpu_latest=gpus)
        results = await _make_analytics(store=store).get_gpu_efficiency()
        self.assertLessEqual(results[0]["score"], 100)


# ========== 规则优化建议测试 ==========


class RuleBasedSuggestionTests(unittest.TestCase):
    """规则驱动的优化建议"""

    def setUp(self):
        self.analytics = _make_analytics()

    def test_low_util_high_power_triggers(self):
        """低利用率+高功耗触发建议"""
        gpus = [{
            "gpu_index": 0, "gpu_utilization": 15,
            "power_usage": 200, "power_limit": 350,
            "temperature": 60,
        }]
        suggestions = self.analytics._generate_rule_based_suggestions(gpus)
        self.assertGreater(len(suggestions), 0)
        self.assertNotEqual(suggestions[0]["action"], "none")

    def test_good_state_no_action(self):
        """状态良好时返回'无需调整'"""
        gpus = [{
            "gpu_index": 0, "gpu_utilization": 90,
            "power_usage": 280, "power_limit": 350,
            "temperature": 60,
        }]
        suggestions = self.analytics._generate_rule_based_suggestions(gpus)
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["action"], "none")

    def test_high_temp_triggers(self):
        """高温(≥75°C)触发建议"""
        gpus = [{
            "gpu_index": 0, "gpu_utilization": 60,
            "power_usage": 300, "power_limit": 350,
            "temperature": 80,
        }]
        suggestions = self.analytics._generate_rule_based_suggestions(gpus)
        has_temp = any("温度" in s.get("reason", "") or "降温" in s.get("reason", "")
                       for s in suggestions)
        self.assertTrue(has_temp, "高温应触发降温建议")

    def test_dedup_per_gpu(self):
        """同一 GPU 只保留节省最大的建议"""
        gpus = [{
            "gpu_index": 0, "gpu_utilization": 10,
            "power_usage": 300, "power_limit": 350,
            "temperature": 80,
        }]
        suggestions = self.analytics._generate_rule_based_suggestions(gpus)
        gpu0_suggestions = [s for s in suggestions
                            if s.get("target", {}).get("gpu_index") == 0]
        self.assertLessEqual(len(gpu0_suggestions), 1,
                             "同一GPU只保留一个建议")

    def test_multiple_gpus(self):
        """多 GPU 各自独立生成建议"""
        gpus = [
            {"gpu_index": 0, "gpu_utilization": 10, "power_usage": 300,
             "power_limit": 350, "temperature": 60},
            {"gpu_index": 1, "gpu_utilization": 5, "power_usage": 250,
             "power_limit": 350, "temperature": 60},
        ]
        suggestions = self.analytics._generate_rule_based_suggestions(gpus)
        gpu_indices = {s.get("target", {}).get("gpu_index") for s in suggestions}
        self.assertIn(0, gpu_indices)
        self.assertIn(1, gpu_indices)


# ========== 时段分类测试 ==========


class TimePeriodTests(unittest.TestCase):
    """时段分类验证"""

    def test_peak_hours(self):
        """高峰时段正确"""
        for h in [9, 10, 11, 14, 15, 16, 17]:
            self.assertEqual(_classify_hour(h), "peak", f"{h}时应为高峰")

    def test_valley_hours(self):
        """低谷时段正确"""
        for h in [22, 23, 0, 1, 2, 3, 4, 5]:
            self.assertEqual(_classify_hour(h), "valley", f"{h}时应为低谷")

    def test_normal_hours(self):
        """平峰时段正确"""
        for h in [6, 7, 8, 12, 13, 18, 19, 20, 21]:
            self.assertEqual(_classify_hour(h), "normal", f"{h}时应为平峰")


# ========== 常量验证 ==========


class ConstantsTests(unittest.TestCase):
    """核心常量正确性"""

    def test_carbon_factor(self):
        """碳排放因子来自国网2023数据"""
        self.assertAlmostEqual(CARBON_FACTOR, 0.5703)

    def test_electricity_price(self):
        """商业电价"""
        self.assertAlmostEqual(ELECTRICITY_PRICE, 0.85)

    def test_carbon_calculation(self):
        """1kWh 对应碳排放量"""
        kwh = 10.0
        co2 = kwh * CARBON_FACTOR
        self.assertAlmostEqual(co2, 5.703, places=3)


if __name__ == "__main__":
    unittest.main()
