"""GPU任务/进程监控 - 获取占用真实 GPU 的进程列表。"""

import time
from typing import List

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

from process_policy import classify_process


CACHE_TTL_SECONDS = 2.0
_PROCESS_CACHE = {
    "expires_at": 0.0,
    "cache_key": None,
    "processes": [],
}


def _clone_processes(processes: List[dict]) -> List[dict]:
    return [dict(proc) for proc in processes]


def get_gpu_processes(gpu_index: int) -> List[dict]:
    """获取指定 GPU 上运行的真实进程列表。"""
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
        if PSUTIL_AVAILABLE:
            try:
                process = psutil.Process(proc.pid)
                info["name"] = process.name()
                info["username"] = process.username()
                info["command"] = " ".join(process.cmdline()[:5])
                info["cpu_percent"] = process.cpu_percent()
                info["create_time"] = process.create_time()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        result.append(classify_process(info))
    return result


def get_all_gpu_processes(device_count: int) -> List[dict]:
    """获取所有 GPU 上运行的真实进程。"""
    all_processes = []
    for gpu_index in range(device_count):
        all_processes.extend(get_gpu_processes(gpu_index))
    return all_processes


def get_cached_gpu_processes(device_count: int) -> List[dict]:
    """复用短时间窗口内的进程扫描结果，减少重复 NVML / psutil 调用。"""
    now = time.time()
    if (
        _PROCESS_CACHE["cache_key"] == device_count
        and now < _PROCESS_CACHE["expires_at"]
    ):
        return _clone_processes(_PROCESS_CACHE["processes"])

    processes = get_all_gpu_processes(device_count)
    _PROCESS_CACHE["cache_key"] = device_count
    _PROCESS_CACHE["expires_at"] = now + CACHE_TTL_SECONDS
    _PROCESS_CACHE["processes"] = _clone_processes(processes)
    return _clone_processes(processes)
