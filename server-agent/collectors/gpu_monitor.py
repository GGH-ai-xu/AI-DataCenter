"""GPU监控采集模块 - 通过pynvml直接读取GPU状态"""

import time
from typing import List, Optional

try:
    import pynvml
    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False


class GPUMonitor:
    """GPU状态采集器，支持多卡环境"""

    def __init__(self):
        self._initialized = False
        self._device_count = 0

    def init(self):
        """初始化NVML库"""
        if not NVML_AVAILABLE:
            return
        try:
            pynvml.nvmlInit()
            self._device_count = pynvml.nvmlDeviceGetCount()
            self._initialized = True
        except pynvml.NVMLError:
            self._initialized = False

    def shutdown(self):
        """释放NVML资源"""
        if self._initialized:
            try:
                pynvml.nvmlShutdown()
            except pynvml.NVMLError:
                pass
            self._initialized = False

    @property
    def device_count(self) -> int:
        return self._device_count

    def get_gpu_info(self, index: int) -> Optional[dict]:
        """获取单张GPU的完整状态信息"""
        if not self._initialized or index >= self._device_count:
            return None
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(index)
            # 基础信息
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8")

            # 温度（摄氏度）
            temperature = pynvml.nvmlDeviceGetTemperature(
                handle, pynvml.NVML_TEMPERATURE_GPU
            )

            # 功耗（毫瓦 → 瓦）
            power_usage = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
            power_limit = pynvml.nvmlDeviceGetEnforcedPowerLimit(handle) / 1000.0

            # 利用率
            utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)

            # 显存
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)

            # 风扇转速（百分比）
            try:
                fan_speed = pynvml.nvmlDeviceGetFanSpeed(handle)
            except pynvml.NVMLError:
                fan_speed = 0

            # 时钟频率
            try:
                clock_sm = pynvml.nvmlDeviceGetClockInfo(
                    handle, pynvml.NVML_CLOCK_SM
                )
                clock_mem = pynvml.nvmlDeviceGetClockInfo(
                    handle, pynvml.NVML_CLOCK_MEM
                )
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


# 模块单例
gpu_monitor = GPUMonitor()
