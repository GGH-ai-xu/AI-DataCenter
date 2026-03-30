"""任务管理API - 进程查询、暂停/恢复/终止、优先级设置"""

from fastapi import APIRouter, HTTPException

from app.models.schemas import TaskActionRequest, TaskPriorityUpdate

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


@router.get("/")
async def get_tasks():
    """获取所有GPU进程列表（含优先级信息）"""
    from app.main import app_state
    processes = await app_state.agent.get_processes()
    priorities = await app_state.store.get_all_task_priorities()
    for proc in processes:
        proc["priority"] = priorities.get(proc["pid"], "normal")
    return {"processes": app_state.privacy.sanitize_processes(processes)}


def _ensure_risk_acknowledged(req: TaskActionRequest, label: str):
    if req.dry_run:
        return
    if not req.acknowledge_risk:
        raise HTTPException(status_code=400, detail=f"{label}属于真实执行，请先确认风险")


async def _apply_task_action(req: TaskActionRequest, label: str, action_name: str):
    from app.main import app_state

    _ensure_risk_acknowledged(req, label)
    if req.dry_run:
        # 记录演练模式审计日志
        try:
            await app_state.store.save_audit_log(
                action=action_name,
                target=str(req.pid),
                reason=f"手动{label}（演练）",
                operator="user",
                source="manual",
                dry_run=True,
                success=True,
                risk_level="high" if action_name == "terminate_task" else "medium",
                detail=f"PID {req.pid}",
            )
        except Exception:
            pass
        return {
            "success": True,
            "dry_run": True,
            "applied": False,
            "action": action_name,
            "pid": req.pid,
            "message": f"已生成{label}演练结果，未对真实进程生效",
        }

    action_map = {
        "pause_task": app_state.agent.pause_task,
        "resume_task": app_state.agent.resume_task,
        "terminate_task": app_state.agent.terminate_task,
    }
    result = await action_map[action_name](req.pid)
    success = bool(result.get("success"))
    # 记录真实执行审计日志
    try:
        await app_state.store.save_audit_log(
            action=action_name,
            target=str(req.pid),
            reason=f"手动{label}",
            operator="user",
            source="manual",
            dry_run=False,
            success=success,
            error_message=result.get("error", "") if not success else "",
            risk_level="high" if action_name == "terminate_task" else "medium",
            detail=f"PID {req.pid}",
        )
    except Exception:
        pass
    if not success:
        raise HTTPException(status_code=400, detail=result.get("error", "操作失败"))
    result["dry_run"] = False
    result["applied"] = True
    result["action"] = action_name
    result["pid"] = req.pid
    return result


@router.post("/pause")
async def pause_task(req: TaskActionRequest):
    """暂停进程"""
    return await _apply_task_action(req, "暂停任务", "pause_task")


@router.post("/resume")
async def resume_task(req: TaskActionRequest):
    """恢复进程"""
    return await _apply_task_action(req, "恢复任务", "resume_task")


@router.post("/terminate")
async def terminate_task(req: TaskActionRequest):
    """终止进程"""
    return await _apply_task_action(req, "终止任务", "terminate_task")


@router.post("/priority")
async def set_priority(req: TaskPriorityUpdate):
    """设置任务优先级"""
    from app.main import app_state
    await app_state.store.set_task_priority(req.pid, req.priority)
    # 记录优先级调整审计日志
    try:
        await app_state.store.save_audit_log(
            action="set_task_priority",
            target=str(req.pid),
            reason=f"手动调整优先级为 {req.priority}",
            operator="user",
            source="manual",
            dry_run=False,
            success=True,
            risk_level="low",
            detail=f"PID {req.pid} -> {req.priority}",
        )
    except Exception:
        pass
    return {"success": True, "pid": req.pid, "priority": req.priority}
