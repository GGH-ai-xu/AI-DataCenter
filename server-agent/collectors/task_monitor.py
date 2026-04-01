"""GPU任务/进程监控 - 获取占用GPU的进程列表"""

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


# 模拟进程（无真实GPU时使用）
_SIM_PROCESSES = [
    {"pid": 12481, "gpu_index": 0, "gpu_memory_used": 18 * 1073741824, "name": "python",
     "username": "researcher", "command": "python train_llm.py --model gpt2-xl --epochs 100",
     "cpu_percent": 45.2, "priority": "urgent"},
    {"pid": 13302, "gpu_index": 1, "gpu_memory_used": 9 * 1073741824, "name": "python",
     "username": "api-server", "command": "python serve.py --port 8080 --model chat",
     "cpu_percent": 12.8, "priority": "normal"},
    {"pid": 14156, "gpu_index": 2, "gpu_memory_used": 14 * 1073741824, "name": "python",
     "username": "researcher", "command": "python finetune.py --dataset alpaca --lr 2e-5",
     "cpu_percent": 62.1, "priority": "normal"},
    {"pid": 15789, "gpu_index": 3, "gpu_memory_used": 2 * 1073741824, "name": "python",
     "username": "student", "command": "python test_inference.py --batch 8",
     "cpu_percent": 3.4, "priority": "deferrable"},
]

CACHE_TTL_SECONDS = 2.0
_PROCESS_CACHE = {
    "expires_at": 0.0,
    "cache_key": None,
    "processes": [],
}


def _clone_processes(processes: List[dict]) -> List[dict]:
    return [dict(proc) for proc in processes]


def get_gpu_processes(gpu_index: int) -> List[dict]:
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
        if PSUTIL_AVAILABLE:
            try:
                p = psutil.Process(proc.pid)
                info["name"] = p.name()
                info["username"] = p.username()
                info["command"] = " ".join(p.cmdline()[:5])
                info["cpu_percent"] = p.cpu_percent()
                info["create_time"] = p.create_time()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        result.append(classify_process(info))
    return result


def get_all_gpu_processes(device_count: int, simulate: bool = False) -> List[dict]:
    """获取所有GPU上的进程"""
    if simulate:
        now = time.time()
        return [
            classify_process({**p, "create_time": now - (i + 1) * 3600})
            for i, p in enumerate(_SIM_PROCESSES)
        ]
    all_procs = []
    for i in range(device_count):
        all_procs.extend(get_gpu_processes(i))
    return all_procs


def get_cached_gpu_processes(
    device_count: int,
    simulate: bool = False,
) -> List[dict]:
    """复用短时间窗口内的进程扫描结果，减少重复 NVML / psutil 调用。"""
    cache_key = (device_count, simulate)
    now = time.time()
    if (
        _PROCESS_CACHE["cache_key"] == cache_key
        and now < _PROCESS_CACHE["expires_at"]
    ):
        return _clone_processes(_PROCESS_CACHE["processes"])

    processes = get_all_gpu_processes(device_count, simulate=simulate)
    _PROCESS_CACHE["cache_key"] = cache_key
    _PROCESS_CACHE["expires_at"] = now + CACHE_TTL_SECONDS
    _PROCESS_CACHE["processes"] = _clone_processes(processes)
    return _clone_processes(processes)
