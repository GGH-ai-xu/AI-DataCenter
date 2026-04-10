"""GPU监控采集模块 - 通过 pynvml 读取真实 GPU 状态。"""

import time
from typing import List, Optional

try:
    import pynvml

    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False


class GPUMonitor:
    """GPU 状态采集器，只返回真实采集结果。"""

    def __init__(self):
        self._initialized = False
        self._nvml_initialized = False
        self._device_count = 0
        self._startup_issue = ""

    def init(self):
        """初始化 NVML；缺少依赖或没有 GPU 时保留空数据状态。"""
        self._initialized = True
        self._nvml_initialized = False
        self._device_count = 0
        self._startup_issue = ""

        if not NVML_AVAILABLE:
            self._startup_issue = "pynvml 未安装，当前无法采集真实 GPU 数据。"
            return

        try:
            pynvml.nvmlInit()
            self._nvml_initialized = True
            self._device_count = int(pynvml.nvmlDeviceGetCount())
        except pynvml.NVMLError as exc:
            self._startup_issue = f"NVML 初始化失败，当前无法采集真实 GPU 数据: {exc}"
            return

        if self._device_count <= 0:
            self._startup_issue = "NVML 已就绪，但当前未检测到真实 GPU。"

    def shutdown(self):
        """释放 NVML 资源。"""
        if not self._nvml_initialized:
            self._initialized = False
            self._device_count = 0
            return

        try:
            pynvml.nvmlShutdown()
        except (pynvml.NVMLError, Exception):
            pass

        self._initialized = False
        self._nvml_initialized = False
        self._device_count = 0

    @property
    def device_count(self) -> int:
        return self._device_count

    @property
    def startup_issue(self) -> str:
        return self._startup_issue

    def get_gpu_info(self, index: int) -> Optional[dict]:
        """获取单张真实 GPU 状态。"""
        if not self._initialized or not self._nvml_initialized:
            return None
        if index < 0 or index >= self._device_count:
            return None

        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(index)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8")

            temperature = pynvml.nvmlDeviceGetTemperature(
                handle,
                pynvml.NVML_TEMPERATURE_GPU,
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
        """获取全部真实 GPU 状态。"""
        if not self._initialized or not self._nvml_initialized or self._device_count <= 0:
            return []

        results = []
        for index in range(self._device_count):
            info = self.get_gpu_info(index)
            if info:
                results.append(info)
        return results


gpu_monitor = GPUMonitor()
