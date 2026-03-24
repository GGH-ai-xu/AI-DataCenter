"""任务控制 - 暂停/恢复/终止GPU进程"""

import os
import signal
import logging
import platform

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == "Windows"


def _validate_pid(pid: int) -> bool:
    """验证PID是否存在"""
    if not PSUTIL_AVAILABLE:
        return False
    return psutil.pid_exists(pid)


def pause_task(pid: int) -> dict:
    """暂停进程（SIGSTOP / Windows suspend）"""
    if not _validate_pid(pid):
        return {"success": False, "error": f"进程 {pid} 不存在"}
    try:
        p = psutil.Process(pid)
        p.suspend()
        logger.info(f"进程 {pid} ({p.name()}) 已暂停")
        return {"success": True, "pid": pid, "action": "paused"}
    except psutil.AccessDenied:
        return {"success": False, "error": f"无权操作进程 {pid}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def resume_task(pid: int) -> dict:
    """恢复进程（SIGCONT / Windows resume）"""
    if not _validate_pid(pid):
        return {"success": False, "error": f"进程 {pid} 不存在"}
    try:
        p = psutil.Process(pid)
        p.resume()
        logger.info(f"进程 {pid} ({p.name()}) 已恢复")
        return {"success": True, "pid": pid, "action": "resumed"}
    except psutil.AccessDenied:
        return {"success": False, "error": f"无权操作进程 {pid}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def terminate_task(pid: int) -> dict:
    """终止进程（SIGTERM）"""
    if not _validate_pid(pid):
        return {"success": False, "error": f"进程 {pid} 不存在"}
    try:
        p = psutil.Process(pid)
        name = p.name()
        p.terminate()
        logger.info(f"进程 {pid} ({name}) 已终止")
        return {"success": True, "pid": pid, "action": "terminated"}
    except psutil.AccessDenied:
        return {"success": False, "error": f"无权操作进程 {pid}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
