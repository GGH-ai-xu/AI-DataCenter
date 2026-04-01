"""系统资源监控 - CPU、内存、磁盘、网络通过psutil采集"""

import time
from typing import List

import psutil


_CPU_SAMPLER_READY = False


def _sample_cpu_percent(percpu: bool = False):
    global _CPU_SAMPLER_READY
    if not _CPU_SAMPLER_READY:
        psutil.cpu_percent(interval=None)
        psutil.cpu_percent(interval=None, percpu=True)
        _CPU_SAMPLER_READY = True
    return psutil.cpu_percent(interval=None, percpu=percpu)


def get_system_info() -> dict:
    """获取系统级资源信息（基础版，兼容原有接口）"""
    cpu_percent = _sample_cpu_percent()
    mem = psutil.virtual_memory()
    return {
        "cpu_percent": cpu_percent,
        "cpu_count": psutil.cpu_count(),
        "memory_total": mem.total,
        "memory_used": mem.used,
        "memory_percent": mem.percent,
        "timestamp": time.time(),
    }


def get_system_detail() -> dict:
    """获取完整系统资源信息（含磁盘、网络、每核CPU）"""
    cpu_percent = _sample_cpu_percent()
    cpu_per_core = _sample_cpu_percent(percpu=True)
    mem = psutil.virtual_memory()

    # 磁盘信息
    disks = []  # type: List[dict]
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
            })
        except (PermissionError, OSError):
            pass

    # 网络流量（全局累计值，前端可做差值计算速率）
    net = psutil.net_io_counters()
    network = {
        "bytes_sent": net.bytes_sent,
        "bytes_recv": net.bytes_recv,
        "packets_sent": net.packets_sent,
        "packets_recv": net.packets_recv,
    }

    # 系统负载（Linux only）
    try:
        load_avg = list(psutil.getloadavg())
    except (AttributeError, OSError):
        load_avg = [0.0, 0.0, 0.0]

    # 系统启动时间
    boot_time = psutil.boot_time()

    return {
        "cpu_percent": cpu_percent,
        "cpu_count": psutil.cpu_count(),
        "cpu_count_physical": psutil.cpu_count(logical=False),
        "cpu_per_core": cpu_per_core,
        "load_avg": load_avg,
        "memory_total": mem.total,
        "memory_used": mem.used,
        "memory_available": mem.available,
        "memory_percent": mem.percent,
        "swap_total": psutil.swap_memory().total,
        "swap_used": psutil.swap_memory().used,
        "swap_percent": psutil.swap_memory().percent,
        "disks": disks,
        "network": network,
        "boot_time": boot_time,
        "timestamp": time.time(),
    }
