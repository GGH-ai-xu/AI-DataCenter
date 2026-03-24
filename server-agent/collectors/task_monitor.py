"""GPU任务/进程监控 - 获取占用GPU的进程列表"""

import time
from typing import Optional

try:
    import pynvml
    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


def get_gpu_processes(gpu_index: int) -> list[dict]:
    """获取指定GPU上运行的进程列表"""
    if not NVML_AVAILABLE:
        return []
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
        processes = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
    except pynvml.NVMLError:
        return []

    result = []
    for proc in processes:
        info = {
            "pid": proc.pid,
            "gpu_index": gpu_index,
            "gpu_memory_used": proc.usedGpuMemory or 0,
            "name": "unknown",
            "username": "unknown",
            "command": "",
            "cpu_percent": 0.0,
            "create_time": 0,
        }
        # 用psutil补充进程详情
        if PSUTIL_AVAILABLE:
            try:
                p = psutil.Process(proc.pid)
                info["name"] = p.name()
                info["username"] = p.username()
                info["command"] = " ".join(p.cmdline()[:5])  # 截取前5段
                info["cpu_percent"] = p.cpu_percent()
                info["create_time"] = p.create_time()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        result.append(info)
    return result


def get_all_gpu_processes(device_count: int) -> list[dict]:
    """获取所有GPU上的进程"""
    all_procs = []
    for i in range(device_count):
        all_procs.extend(get_gpu_processes(i))
    return all_procs
