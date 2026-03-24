"""告警引擎 - 基于阈值的实时告警检测"""

import time
import logging

logger = logging.getLogger(__name__)


class AlertEngine:
    """告警引擎 - 检测GPU指标是否超过阈值"""

    def __init__(self, temp_threshold: int = 85, power_threshold: int = 320,
                 memory_threshold: int = 90):
        self.temp_threshold = temp_threshold
        self.power_threshold = power_threshold
        self.memory_threshold = memory_threshold
        # 防重复告警：记录最近已触发的告警（key -> timestamp）
        self._recent_alerts: dict[str, float] = {}
        # 记录各GPU当前是否处于告警状态（用于恢复检测）
        self._active_alerts: dict[str, bool] = {}
        self._cooldown = 60  # 同类告警冷却时间（秒）

    def check_gpu(self, gpu: dict) -> list[dict]:
        """检查单张GPU的指标，返回告警列表"""
        alerts = []
        idx = gpu.get("index", 0)
        now = time.time()

        # 温度告警
        temp = gpu.get("temperature", 0)
        temp_key = f"{idx}:temperature"
        if temp >= 90:
            self._active_alerts[temp_key] = True
            alerts.append(self._make_alert(
                idx, "temperature", "critical",
                f"GPU{idx} 温度过高: {temp}°C (临界值90°C)，需立即降频",
                temp, 90, now
            ))
        elif temp >= self.temp_threshold:
            self._active_alerts[temp_key] = True
            alerts.append(self._make_alert(
                idx, "temperature", "warning",
                f"GPU{idx} 温度偏高: {temp}°C (阈值{self.temp_threshold}°C)",
                temp, self.temp_threshold, now
            ))
        elif self._active_alerts.get(temp_key):
            # 温度恢复正常，发送恢复通知
            self._active_alerts[temp_key] = False
            self._clear_cooldown(idx, "temperature")
            alerts.append(self._make_alert(
                idx, "temperature", "info",
                f"GPU{idx} 温度恢复正常: {temp}°C",
                temp, self.temp_threshold, now
            ))

        # 功耗告警
        power = gpu.get("power_usage", 0)
        power_key = f"{idx}:power"
        if power >= self.power_threshold:
            self._active_alerts[power_key] = True
            alerts.append(self._make_alert(
                idx, "power", "warning",
                f"GPU{idx} 功耗较高: {power}W (阈值{self.power_threshold}W)",
                power, self.power_threshold, now
            ))
        elif self._active_alerts.get(power_key):
            self._active_alerts[power_key] = False
            self._clear_cooldown(idx, "power")

        # 显存告警
        mem_total = gpu.get("memory_total", 0)
        mem_used = gpu.get("memory_used", 0)
        if isinstance(mem_total, (int, float)) and mem_total > 0:
            mem_pct = mem_used / mem_total * 100
            if mem_pct >= self.memory_threshold:
                alerts.append(self._make_alert(
                    idx, "memory", "warning",
                    f"GPU{idx} 显存使用率: {mem_pct:.1f}% (阈值{self.memory_threshold}%)",
                    mem_pct, self.memory_threshold, now
                ))

        # 过滤冷却中的重复告警
        return [a for a in alerts if self._should_fire(a)]

    def check_all_gpus(self, gpus: list[dict]) -> list[dict]:
        """检查所有GPU"""
        all_alerts = []
        for gpu in gpus:
            all_alerts.extend(self.check_gpu(gpu))
        return all_alerts

    def _make_alert(self, gpu_index: int, alert_type: str, severity: str,
                    message: str, value: float, threshold: float, ts: float) -> dict:
        return {
            "gpu_index": gpu_index,
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "value": value,
            "threshold": threshold,
            "timestamp": ts,
        }

    def _should_fire(self, alert: dict) -> bool:
        """判断告警是否应触发（冷却去重）"""
        key = f"{alert['gpu_index']}:{alert['alert_type']}:{alert['severity']}"
        now = alert["timestamp"]
        last = self._recent_alerts.get(key, 0)
        if now - last < self._cooldown:
            return False
        self._recent_alerts[key] = now
        return True

    def _clear_cooldown(self, gpu_index: int, alert_type: str):
        """清除指定GPU和类型的冷却记录（恢复后重新计时）"""
        keys_to_remove = [
            k for k in self._recent_alerts
            if k.startswith(f"{gpu_index}:{alert_type}:")
        ]
        for k in keys_to_remove:
            del self._recent_alerts[k]
