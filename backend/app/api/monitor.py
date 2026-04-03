"""监控观察API - 训练进度、用户统计、任务时间线、系统详情"""

import time

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/monitor", tags=["Monitor"])

_LOW_SIGNAL_COMMAND_KEYWORDS = (
    "--type=gpu-process",
    "--type=utility",
    "--utility-sub-type=",
    "--gpu-preferences=",
    "msedge.exe",
    "chrome.exe",
    "edgewebview",
    "gpugovernanceworkbench",
    "共享治理平台",
)

_LOW_SIGNAL_MEMORY_BYTES = 64 * 1024 * 1024


def _selected_gpu_indexes(app_state) -> list[int]:
    return app_state.import_context.selected_gpu_indexes()


def _filter_training_logs(logs: list[dict], gpu_indexes: list[int]) -> list[dict]:
    allowed = set(gpu_indexes)
    return [
        item
        for item in logs
        if int(item.get("gpu_index", -1)) in allowed
    ]


def _is_low_signal_timeline_entry(entry: dict) -> bool:
    """过滤桌面壳、浏览器 GPU helper 等低价值陪跑历史，避免污染观察页。"""
    command = str(entry.get("command") or "").lower()
    username = str(entry.get("username") or "").strip().lower()
    try:
        gpu_memory_used = int(entry.get("gpu_memory_used") or 0)
    except (TypeError, ValueError):
        gpu_memory_used = 0

    if any(keyword in command for keyword in _LOW_SIGNAL_COMMAND_KEYWORDS):
        return True

    if gpu_memory_used > _LOW_SIGNAL_MEMORY_BYTES:
        return False

    if username in {"", "unknown"}:
        return True

    return False


@router.get("/system-detail")
async def get_system_detail():
    """获取完整系统资源信息（CPU每核、磁盘、网络）"""
    from app.main import app_state
    detail = await app_state.agent.get_system_detail()
    if not detail:
        # 降级：返回基础信息
        basic = await app_state.agent.get_system_info()
        return basic or {"error": "Agent不可用"}
    return detail


@router.get("/training")
async def get_training_progress():
    """获取训练进度数据（epoch/loss/accuracy曲线）"""
    from app.main import app_state
    logs = await app_state.agent.get_training_logs()
    logs = _filter_training_logs(logs, _selected_gpu_indexes(app_state))
    return {"training": app_state.privacy.sanitize_training_logs(logs)}


@router.get("/users")
async def get_user_stats():
    """按用户统计当前GPU资源占用"""
    from app.main import app_state
    gpu_indexes = _selected_gpu_indexes(app_state)

    # 从数据库获取用户统计
    db_stats = await app_state.store.get_user_stats(gpu_indexes=gpu_indexes)

    # 补充实时进程信息
    processes = await app_state.agent.get_processes()
    processes = app_state.import_context.filter_processes(processes)
    # 按用户聚合当前实时数据
    user_live = {}
    for proc in processes:
        user = proc.get("username", "unknown")
        if user not in user_live:
            user_live[user] = {
                "username": user,
                "gpu_indices": set(),
                "task_count": 0,
                "total_memory": 0,
                "processes": [],
            }
        user_live[user]["gpu_indices"].add(proc.get("gpu_index", -1))
        user_live[user]["task_count"] += 1
        user_live[user]["total_memory"] += proc.get("gpu_memory_used", 0)
        user_live[user]["processes"].append({
            "pid": proc.get("pid"),
            "gpu_index": proc.get("gpu_index"),
            "command": proc.get("command", ""),
            "gpu_memory_used": proc.get("gpu_memory_used", 0),
            "create_time": proc.get("create_time", 0),
        })

    # 合并输出
    result = []
    for user, live in user_live.items():
        entry = {
            "username": user,
            "gpu_count": len(live["gpu_indices"]),
            "gpu_indices": sorted(live["gpu_indices"]),
            "task_count": live["task_count"],
            "total_memory": live["total_memory"],
            "processes": live["processes"],
        }
        # 从DB补充历史时间
        for db in db_stats:
            if db["username"] == user:
                entry["earliest_start"] = db.get("earliest_start", 0)
                break
        result.append(entry)

    return {"users": app_state.privacy.sanitize_user_stats(result)}


@router.get("/task-history")
async def get_task_history(hours: float = 24):
    """获取任务历史时间线"""
    from app.main import app_state
    timeline = await app_state.store.get_process_timeline(
        hours,
        gpu_indexes=_selected_gpu_indexes(app_state),
    )
    timeline = [item for item in timeline if not _is_low_signal_timeline_entry(item)]
    return {
        "timeline": app_state.privacy.sanitize_timeline(timeline),
        "hours": hours,
    }


@router.get("/replay")
async def get_monitor_replay(
    hours: float = Query(default=24.0, ge=1, le=168),
    bucket_minutes: int = Query(default=10, ge=1, le=60),
):
    """获取治理回放帧，用于时序复盘。"""
    from app.main import app_state

    frames = await app_state.store.get_replay_frames(
        hours,
        bucket_minutes,
        gpu_indexes=_selected_gpu_indexes(app_state),
    )
    return {
        "hours": hours,
        "bucket_minutes": bucket_minutes,
        "frames": frames,
    }
