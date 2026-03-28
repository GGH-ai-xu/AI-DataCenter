"""GPU监控采集模块 - 通过pynvml直接读取GPU状态

无NVIDIA GPU时自动切换为模拟模式，生成逼真的4卡数据，保证全链路可用。
"""

import math
import random
import time
from typing import List, Optional

try:
    import pynvml
    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False


# ========== 模拟GPU配置（无真实GPU时使用） ==========
_SIM_GPUS = [
    {"name": "NVIDIA GeForce RTX 4090", "mem_total": 24 * 1073741824, "tdp": 350},
    {"name": "NVIDIA GeForce RTX 4090", "mem_total": 24 * 1073741824, "tdp": 350},
    {"name": "NVIDIA GeForce RTX 4080", "mem_total": 16 * 1073741824, "tdp": 320},
    {"name": "NVIDIA GeForce RTX 4080", "mem_total": 16 * 1073741824, "tdp": 320},
]

# 每张GPU的基准负载场景
_SIM_PROFILES = [
    {"util": 82, "power_pct": 0.78, "temp": 70, "mem_pct": 0.76},  # GPU0: 大模型训练
    {"util": 45, "power_pct": 0.52, "temp": 56, "mem_pct": 0.40},  # GPU1: 推理服务
    {"util": 90, "power_pct": 0.88, "temp": 76, "mem_pct": 0.89},  # GPU2: 微调训练
    {"util": 18, "power_pct": 0.28, "temp": 42, "mem_pct": 0.15},  # GPU3: 轻负载
]

# 功耗限制覆盖（模拟调频效果）
_sim_power_limits = {}


def _time_factor() -> float:
    """基于时段的负载波动系数：高峰1.1，平峰1.0，低谷0.7"""
    h = time.localtime().tm_hour
    if 9 <= h < 12 or 14 <= h < 18:
        return 1.05 + random.random() * 0.1
    elif 22 <= h or h < 6:
        return 0.6 + random.random() * 0.15
    return 0.9 + random.random() * 0.1


def _sim_gpu(index: int) -> dict:
    """生成单张模拟GPU数据"""
    cfg = _SIM_GPUS[index]
    prof = _SIM_PROFILES[index]
    tf = _time_factor()

    util = max(3, min(100, int(prof["util"] * tf + random.randint(-5, 5))))
    power_limit = _sim_power_limits.get(index, cfg["tdp"])
    power_pct = prof["power_pct"] * tf
    power = min(power_limit, cfg["tdp"] * power_pct) + random.uniform(-8, 8)
    power = max(30, min(power_limit, power))
    temp = max(32, min(94, int(prof["temp"] * tf + random.randint(-2, 3))))
    mem_pct = max(0.05, min(0.96, prof["mem_pct"] + random.uniform(-0.03, 0.03)))
    mem_used = int(cfg["mem_total"] * mem_pct)

    return {
        "index": index,
        "name": cfg["name"],
        "temperature": temp,
        "power_usage": round(power, 1),
        "power_limit": round(power_limit, 1),
        "gpu_utilization": util,
        "memory_utilization": int(mem_pct * 100),
        "memory_used": mem_used,
        "memory_total": cfg["mem_total"],
        "memory_free": cfg["mem_total"] - mem_used,
        "fan_speed": max(30, min(100, int(temp * 1.05 + random.randint(-3, 5)))),
        "clock_sm": random.randint(1200, 1900),
        "clock_mem": random.randint(9000, 9800),
        "timestamp": time.time(),
    }


class GPUMonitor:
    """GPU状态采集器，支持多卡环境，无GPU时自动模拟"""

    def __init__(self):
        self._initialized = False
        self._device_count = 0
        self._simulate = False

    def init(self):
        """初始化NVML库，失败则切换模拟模式"""
        if not NVML_AVAILABLE:
            self._start_simulation()
            return
        try:
            pynvml.nvmlInit()
            count = pynvml.nvmlDeviceGetCount()
            if count > 0:
                self._device_count = count
                self._initialized = True
                return
        except pynvml.NVMLError:
            pass
        self._start_simulation()

    def _start_simulation(self):
        """启动模拟模式"""
        self._simulate = True
        self._device_count = len(_SIM_GPUS)
        self._initialized = True

    @property
    def is_simulated(self) -> bool:
        return self._simulate

    def shutdown(self):
        """释放NVML资源"""
        if self._initialized and not self._simulate:
            try:
                pynvml.nvmlShutdown()
            except (pynvml.NVMLError, Exception):
                pass
        self._initialized = False

    @property
    def device_count(self) -> int:
        return self._device_count

    def get_gpu_info(self, index: int) -> Optional[dict]:
        """获取单张GPU的完整状态信息"""
        if not self._initialized or index >= self._device_count:
            return None

        if self._simulate:
            return _sim_gpu(index)

        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(index)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8")

            temperature = pynvml.nvmlDeviceGetTemperature(
                handle, pynvml.NVML_TEMPERATURE_GPU
            )
            power_usage = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
            power_limit = pynvml.nvmlDeviceGetEnforcedPowerLimit(handle) / 1000.0
            utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)

            try:
                fan_speed = pynvml.nvmlDeviceGetFanSpeed(handle)
            except pynvml.NVMLError:
                fan_speed = 0

            try:
                clock_sm = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_SM)
                clock_mem = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM)
            except pynvml.NVMLError:
                clock_sm = 0
                clock_mem = 0

            return {
                "index": index,
                "name": name,
                "temperature": temperature,
                "power_usage": round(power_usage, 1),
                "power_limit": round(power_limit, 1),
                "gpu_utilization": utilization.gpu,
                "memory_utilization": utilization.memory,
                "memory_used": mem_info.used,
                "memory_total": mem_info.total,
                "memory_free": mem_info.free,
                "fan_speed": fan_speed,
                "clock_sm": clock_sm,
                "clock_mem": clock_mem,
                "timestamp": time.time(),
            }
        except pynvml.NVMLError:
            return None

    def get_all_gpus(self) -> List[dict]:
        """获取所有GPU的状态"""
        results = []
        for i in range(self._device_count):
            info = self.get_gpu_info(i)
            if info:
                results.append(info)
        return results

    def set_sim_power_limit(self, index: int, watts: int):
        """模拟模式下设置功耗限制"""
        _sim_power_limits[index] = watts


# 模块单例
gpu_monitor = GPUMonitor()
