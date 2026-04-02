"""任务控制 - 暂停/恢复/终止GPU进程"""

import logging

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = logging.getLogger(__name__)


def _validate_pid(pid: int) -> bool:
    """验证PID是否存在"""
    if not PSUTIL_AVAILABLE:
        return False
    return psutil.pid_exists(pid)


def _read_process_snapshot(pid: int) -> dict | None:
    """优先从当前 GPU 进程列表读取，再回退到 psutil 快照。"""
    if not PSUTIL_AVAILABLE or not _validate_pid(pid):
        return None

    from collectors.gpu_monitor import gpu_monitor
    from collectors.task_monitor import get_all_gpu_processes
    from process_policy import classify_process

    processes = get_all_gpu_processes(gpu_monitor.device_count)
    for proc in processes:
        if proc.get("pid") == pid:
            return {**proc, "_from_gpu_process_list": True}

    try:
        proc = psutil.Process(pid)
        return {
            **classify_process(
            {
                "pid": pid,
                "gpu_index": -1,
                "gpu_memory_used": 0,
                "name": proc.name(),
                "username": proc.username(),
                "command": " ".join(proc.cmdline()[:8]),
                "cpu_percent": proc.cpu_percent(),
                "create_time": proc.create_time(),
                "priority": "normal",
            }
            ),
            "_from_gpu_process_list": False,
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def _ensure_manageable(pid: int) -> tuple[dict | None, dict | None]:
    """确认目标是当前允许治理的 GPU 任务。"""
    if not _validate_pid(pid):
        return None, {"success": False, "error": f"进程 {pid} 不存在"}

    snapshot = _read_process_snapshot(pid)
    if not snapshot:
        return None, {"success": False, "error": f"无法获取进程 {pid} 的实时信息"}
    if not snapshot.get("_from_gpu_process_list"):
        return snapshot, {"success": False, "error": f"进程 {pid} 不在当前 GPU 任务列表中，无法执行治理动作"}

    if not snapshot.get("manageable", True):
        reason = snapshot.get("manageable_reason") or "该进程不允许执行治理动作"
        return snapshot, {"success": False, "error": reason}

    return snapshot, None


def pause_task(pid: int) -> dict:
    """暂停进程（SIGSTOP / Windows suspend）"""
    snapshot, error = _ensure_manageable(pid)
    if error:
        return error
    try:
        p = psutil.Process(pid)
        p.suspend()
        logger.info(f"进程 {pid} ({p.name()}) 已暂停")
        return {
            "success": True,
            "pid": pid,
            "action": "paused",
            "process_name": snapshot.get("name") if snapshot else p.name(),
        }
    except psutil.AccessDenied:
        return {"success": False, "error": f"无权操作进程 {pid}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def resume_task(pid: int) -> dict:
    """恢复进程（SIGCONT / Windows resume）"""
    snapshot, error = _ensure_manageable(pid)
    if error:
        return error
    try:
        p = psutil.Process(pid)
        p.resume()
        logger.info(f"进程 {pid} ({p.name()}) 已恢复")
        return {
            "success": True,
            "pid": pid,
            "action": "resumed",
            "process_name": snapshot.get("name") if snapshot else p.name(),
        }
    except psutil.AccessDenied:
        return {"success": False, "error": f"无权操作进程 {pid}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def terminate_task(pid: int) -> dict:
    """终止进程（SIGTERM）"""
    snapshot, error = _ensure_manageable(pid)
    if error:
        return error
    try:
        p = psutil.Process(pid)
        name = p.name()
        p.terminate()
        try:
            p.wait(timeout=3)
            forced = False
        except psutil.TimeoutExpired:
            p.kill()
            p.wait(timeout=2)
            forced = True
        logger.info(f"进程 {pid} ({name}) 已终止")
        return {
            "success": True,
            "pid": pid,
            "action": "terminated",
            "process_name": snapshot.get("name") if snapshot else name,
            "forced": forced,
        }
    except psutil.TimeoutExpired:
        return {"success": False, "error": f"进程 {pid} 在终止超时后仍未退出"}
    except psutil.AccessDenied:
        return {"success": False, "error": f"无权操作进程 {pid}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
