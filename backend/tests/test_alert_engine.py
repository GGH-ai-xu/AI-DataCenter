"""alert_engine 告警检测单元测试"""

import time
import pytest
from app.services.alert_engine import AlertEngine


@pytest.fixture
def engine():
    """创建默认阈值的告警引擎"""
    return AlertEngine(temp_threshold=85, power_threshold=320, memory_threshold=90)


# ─── 温度告警 ──────────────────────────────────────────────

class TestTemperatureAlerts:
    def test_normal_temp_no_alert(self, engine):
        gpu = {"index": 0, "temperature": 70, "power_usage": 200, "memory_used": 5000, "memory_total": 24000}
        alerts = engine.check_gpu(gpu)
        assert len(alerts) == 0

    def test_warning_temp(self, engine):
        gpu = {"index": 0, "temperature": 87, "power_usage": 200, "memory_used": 5000, "memory_total": 24000}
        alerts = engine.check_gpu(gpu)
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "warning"
        assert alerts[0]["alert_type"] == "temperature"

    def test_critical_temp(self, engine):
        gpu = {"index": 0, "temperature": 92, "power_usage": 200, "memory_used": 5000, "memory_total": 24000}
        alerts = engine.check_gpu(gpu)
        assert any(a["severity"] == "critical" and a["alert_type"] == "temperature" for a in alerts)

    def test_temp_recovery(self, engine):
        gpu_hot = {"index": 0, "temperature": 88, "power_usage": 200, "memory_used": 5000, "memory_total": 24000}
        engine.check_gpu(gpu_hot)

        # 等一下让冷却时间过，然后降温
        engine._cooldown = 0  # 禁用冷却以便测试
        engine._recent_alerts.clear()

        gpu_cool = {"index": 0, "temperature": 70, "power_usage": 200, "memory_used": 5000, "memory_total": 24000}
        alerts = engine.check_gpu(gpu_cool)
        assert any(a["severity"] == "info" and "恢复" in a["message"] for a in alerts)


# ─── 功耗告警 ──────────────────────────────────────────────

class TestPowerAlerts:
    def test_normal_power_no_alert(self, engine):
        gpu = {"index": 0, "temperature": 70, "power_usage": 250, "memory_used": 5000, "memory_total": 24000}
        alerts = engine.check_gpu(gpu)
        assert not any(a["alert_type"] == "power" for a in alerts)

    def test_high_power_alert(self, engine):
        gpu = {"index": 0, "temperature": 70, "power_usage": 330, "memory_used": 5000, "memory_total": 24000}
        alerts = engine.check_gpu(gpu)
        assert any(a["alert_type"] == "power" and a["severity"] == "warning" for a in alerts)


# ─── 显存告警 ──────────────────────────────────────────────

class TestMemoryAlerts:
    def test_normal_memory(self, engine):
        gpu = {"index": 0, "temperature": 70, "power_usage": 200, "memory_used": 10000, "memory_total": 24000}
        alerts = engine.check_gpu(gpu)
        assert not any(a["alert_type"] == "memory" for a in alerts)

    def test_high_memory(self, engine):
        gpu = {"index": 0, "temperature": 70, "power_usage": 200, "memory_used": 22000, "memory_total": 24000}
        alerts = engine.check_gpu(gpu)
        assert any(a["alert_type"] == "memory" for a in alerts)

    def test_zero_total_memory(self, engine):
        """总显存为0时不触发除零错误"""
        gpu = {"index": 0, "temperature": 70, "power_usage": 200, "memory_used": 0, "memory_total": 0}
        alerts = engine.check_gpu(gpu)
        assert not any(a["alert_type"] == "memory" for a in alerts)


# ─── 冷却去重 ──────────────────────────────────────────────

class TestCooldown:
    def test_duplicate_suppressed(self, engine):
        gpu = {"index": 0, "temperature": 88, "power_usage": 200, "memory_used": 5000, "memory_total": 24000}
        alerts1 = engine.check_gpu(gpu)
        alerts2 = engine.check_gpu(gpu)
        # 第二次应被冷却抑制
        assert len(alerts1) >= 1
        assert len(alerts2) == 0

    def test_after_cooldown_fires_again(self, engine):
        engine._cooldown = 0  # 立即冷却
        gpu = {"index": 0, "temperature": 88, "power_usage": 200, "memory_used": 5000, "memory_total": 24000}
        alerts1 = engine.check_gpu(gpu)
        engine._recent_alerts.clear()
        alerts2 = engine.check_gpu(gpu)
        assert len(alerts1) >= 1
        assert len(alerts2) >= 1


# ─── 批量检查 ──────────────────────────────────────────────

class TestCheckAllGpus:
    def test_multiple_gpus(self, engine):
        gpus = [
            {"index": 0, "temperature": 92, "power_usage": 200, "memory_used": 5000, "memory_total": 24000},
            {"index": 1, "temperature": 70, "power_usage": 330, "memory_used": 5000, "memory_total": 24000},
            {"index": 2, "temperature": 70, "power_usage": 200, "memory_used": 5000, "memory_total": 24000},
        ]
        alerts = engine.check_all_gpus(gpus)
        # GPU 0: 临界温度, GPU 1: 高功耗, GPU 2: 正常
        assert len(alerts) >= 2
        gpu_indices = {a["gpu_index"] for a in alerts}
        assert 0 in gpu_indices
        assert 1 in gpu_indices

    def test_empty_gpu_list(self, engine):
        alerts = engine.check_all_gpus([])
        assert alerts == []


# ─── 阈值自定义 ────────────────────────────────────────────

class TestCustomThresholds:
    def test_custom_temp_threshold(self):
        engine = AlertEngine(temp_threshold=70, power_threshold=320, memory_threshold=90)
        gpu = {"index": 0, "temperature": 72, "power_usage": 200, "memory_used": 5000, "memory_total": 24000}
        alerts = engine.check_gpu(gpu)
        assert any(a["alert_type"] == "temperature" for a in alerts)

    def test_custom_power_threshold(self):
        engine = AlertEngine(temp_threshold=85, power_threshold=200, memory_threshold=90)
        gpu = {"index": 0, "temperature": 70, "power_usage": 210, "memory_used": 5000, "memory_total": 24000}
        alerts = engine.check_gpu(gpu)
        assert any(a["alert_type"] == "power" for a in alerts)

    def test_custom_memory_threshold(self):
        engine = AlertEngine(temp_threshold=85, power_threshold=320, memory_threshold=50)
        gpu = {"index": 0, "temperature": 70, "power_usage": 200, "memory_used": 13000, "memory_total": 24000}
        alerts = engine.check_gpu(gpu)
        assert any(a["alert_type"] == "memory" for a in alerts)
