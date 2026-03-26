"""GPU任务/进程监控 - 获取真实占用 GPU 的进程列表"""

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


def get_gpu_processes(gpu_index: int) -> List[dict]:
    """获取指定 GPU 上运行的真实进程列表"""
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
        result.append(info)
    return result


def get_all_gpu_processes(device_count: int) -> List[dict]:
    """获取所有真实 GPU 上的进程"""
    all_procs = []
    for i in range(device_count):
        all_procs.extend(get_gpu_processes(i))
    return all_procs
