"""GPU监控采集模块 - 通过 pynvml 读取真实 GPU 状态

严格只返回真实硬件数据；当未检测到 NVIDIA GPU 或 NVML 不可用时，不再生成任何模拟数据。
"""

import time
from typing import List, Optional

try:
    import pynvml
    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False


class GPUMonitor:
    """GPU 状态采集器，仅支持真实 GPU 数据"""

    def __init__(self):
        self._initialized = False
        self._device_count = 0
        self._last_error = ""

    def init(self):
        """初始化 NVML；失败时保留为 0 卡状态，不进行任何模拟"""
        self._device_count = 0
        self._initialized = True
        self._last_error = ""

        if not NVML_AVAILABLE:
            self._last_error = "pynvml 未安装"
            return

        try:
            pynvml.nvmlInit()
            count = pynvml.nvmlDeviceGetCount()
            self._device_count = count if count > 0 else 0
        except pynvml.NVMLError as e:
            self._last_error = str(e)
            self._device_count = 0

    @property
    def is_simulated(self) -> bool:
        """保留兼容字段，当前版本始终禁用模拟数据"""
        return False

    @property
    def last_error(self) -> str:
        return self._last_error

    def shutdown(self):
        """释放 NVML 资源"""
        if self._initialized and NVML_AVAILABLE:
            try:
                pynvml.nvmlShutdown()
            except (pynvml.NVMLError, Exception):
                pass
        self._initialized = False

    @property
    def device_count(self) -> int:
        return self._device_count

    def get_gpu_info(self, index: int) -> Optional[dict]:
        """获取单张 GPU 的完整状态信息"""
        if not self._initialized or index >= self._device_count or not NVML_AVAILABLE:
            return None

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
        """获取所有真实 GPU 的状态"""
        results = []
        for i in range(self._device_count):
            info = self.get_gpu_info(i)
            if info:
                results.append(info)
        return results


gpu_monitor = GPUMonitor()
