"""系统资源监控 - CPU、内存等通过psutil采集"""

import psutil
import time


def get_system_info() -> dict:
    """获取系统级资源信息"""
    cpu_percent = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    return {
        "cpu_percent": cpu_percent,
        "cpu_count": psutil.cpu_count(),
        "memory_total": mem.total,
        "memory_used": mem.used,
        "memory_percent": mem.percent,
        "timestamp": time.time(),
    }
