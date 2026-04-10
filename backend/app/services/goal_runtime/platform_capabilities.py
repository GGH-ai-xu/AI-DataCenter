from __future__ import annotations

from app.api.cluster_jobs import _load_cluster_nodes
from app.services.goal_runtime.capability import (
    CapabilityDefinition,
    CapabilityManualControl,
)
from app.services.goal_runtime.capability_registry import CapabilityRegistry
from app.services.goal_runtime.schedule_once import run_schedule_once
from app.services.cluster_control.models import JobSpecRecord


SUPPORTED_PROVIDERS = ("http_local", "http_remote", "ssh_linux")


def _manual(
    *,
    label: str,
    description: str,
    required_role: str = "member",
    risk_level: str = "observe",
    approval_policy: str = "direct",
    enabled: bool = True,
) -> CapabilityManualControl:
    return CapabilityManualControl(
        enabled=enabled,
        label=label,
        description=description,
        required_role=required_role,
        risk_level=risk_level,
        approval_policy=approval_policy,
    )


async def _load_filtered_processes(app_state) -> list[dict]:
    processes = await app_state.agent.get_processes()
    return app_state.import_context.filter_processes(processes or [])


def _job_record_from_arguments(arguments: dict) -> JobSpecRecord:
    return JobSpecRecord(
        job_id=str(arguments["job_id"]),
        tenant_id=str(arguments["tenant_id"]),
        project_id=str(arguments["project_id"]),
        queue_id=str(arguments["queue_id"]),
        submitter_id=str(arguments["submitter_id"]),
        job_type=str(arguments["job_type"]),
        entrypoint=str(arguments["entrypoint"]),
        args=tuple(arguments.get("args", ())),
        env=dict(arguments.get("env", {})),
        resource_request=dict(arguments.get("resource_request", {})),
        placement_constraints=dict(arguments.get("placement_constraints", {})),
        priority=int(arguments.get("priority", 50)),
        preemptible=bool(arguments.get("preemptible", True)),
        max_retries=int(arguments.get("max_retries", 0)),
        timeout_seconds=int(arguments.get("timeout_seconds", 0)),
    )


def build_platform_capability_registry(app_state) -> CapabilityRegistry:
    registry = CapabilityRegistry()

    async def read_runtime_snapshot(_context, _arguments):
        gpus = await app_state.agent.get_all_gpus()
        filtered_gpus = app_state.import_context.filter_gpus(gpus or [])
        processes = await _load_filtered_processes(app_state)
        return {
            "gpus": filtered_gpus,
            "processes": processes,
            "budget": app_state.scheduler.get_budget_status(filtered_gpus),
        }

    async def set_power_limit(_context, arguments):
        gpu_index = int(arguments["gpu_index"])
        power_limit = int(arguments["power_limit"])
        app_state.import_context.ensure_gpu_allowed(gpu_index)
        app_state.scheduler.clear_managed_gpu(gpu_index)
        return await app_state.agent.set_power_limit(gpu_index, power_limit)

    async def pause_task(_context, arguments):
        processes = await _load_filtered_processes(app_state)
        pid = int(arguments["pid"])
        app_state.import_context.ensure_process_allowed(pid, processes)
        return await app_state.agent.pause_task(pid)

    async def resume_task(_context, arguments):
        processes = await _load_filtered_processes(app_state)
        pid = int(arguments["pid"])
        app_state.import_context.ensure_process_allowed(pid, processes)
        return await app_state.agent.resume_task(pid)

    async def terminate_task(_context, arguments):
        processes = await _load_filtered_processes(app_state)
        pid = int(arguments["pid"])
        app_state.import_context.ensure_process_allowed(pid, processes)
        return await app_state.agent.terminate_task(pid)

    async def set_task_priority(_context, arguments):
        pid = int(arguments["pid"])
        priority = str(arguments["priority"])
        await app_state.store.set_task_priority(pid, priority)
        return {"success": True, "pid": pid, "priority": priority}

    async def configure_budget(_context, arguments):
        enabled = bool(arguments.get("enabled", True))
        total_power_budget = int(arguments["total_power_budget"])
        app_state.scheduler.configure_budget(enabled, total_power_budget)
        return {
            "success": True,
            "enabled": enabled,
            "total_power_budget": total_power_budget,
        }

    async def run_schedule_once_capability(_context, _arguments):
        return await run_schedule_once(app_state)

    async def submit_job(_context, arguments):
        nodes = await _load_cluster_nodes(app_state)
        job_record = _job_record_from_arguments(arguments)
        plan = await app_state.cluster_control.submit_job(job_record, nodes=nodes)
        job = await app_state.store.get_cluster_job(job_record.job_id)
        return {"job": job, "plan_type": plan.plan_type}

    async def list_jobs(_context, _arguments):
        return {"jobs": await app_state.cluster_control.list_jobs()}

    async def get_job(_context, arguments):
        return await app_state.cluster_control.get_job(str(arguments["job_id"]))

    async def queue_status_read(_context, _arguments):
        return {"queues": await app_state.cluster_control.list_queues()}

    async def pause_job(_context, _arguments):
        raise NotImplementedError("job pause capability is not implemented yet")

    async def resume_job(_context, _arguments):
        raise NotImplementedError("job resume capability is not implemented yet")

    async def cancel_job(_context, _arguments):
        raise NotImplementedError("job cancel capability is not implemented yet")

    registry.register(
        CapabilityDefinition(
            "runtime.snapshot.read",
            "runtime",
            "observe",
            False,
            SUPPORTED_PROVIDERS,
            manual_control=_manual(
                label="读取运行时快照",
                description="读取当前导入范围内的 GPU 与进程快照",
                required_role="observer",
            ),
        ),
        handler=read_runtime_snapshot,
    )
    registry.register(
        CapabilityDefinition(
            "scheduler.power_limit.set",
            "scheduler",
            "runtime_action",
            True,
            SUPPORTED_PROVIDERS,
            manual_control=_manual(
                label="设置 GPU 功耗上限",
                description="对单张 GPU 执行真实限功率",
                risk_level="control",
                approval_policy="confirm_required",
            ),
        ),
        handler=set_power_limit,
    )
    registry.register(
        CapabilityDefinition(
            "tasks.pause",
            "tasks",
            "runtime_action",
            True,
            SUPPORTED_PROVIDERS,
            manual_control=_manual(
                label="暂停任务",
                description="暂停导入范围内的指定任务",
                risk_level="control",
                approval_policy="confirm_required",
            ),
        ),
        handler=pause_task,
    )
    registry.register(
        CapabilityDefinition(
            "tasks.resume",
            "tasks",
            "runtime_action",
            True,
            SUPPORTED_PROVIDERS,
            manual_control=_manual(
                label="恢复任务",
                description="恢复导入范围内的指定任务",
                risk_level="control",
                approval_policy="confirm_required",
            ),
        ),
        handler=resume_task,
    )
    registry.register(
        CapabilityDefinition(
            "tasks.terminate",
            "tasks",
            "runtime_action",
            True,
            SUPPORTED_PROVIDERS,
            manual_control=_manual(
                label="终止任务",
                description="终止导入范围内的指定任务",
                required_role="admin",
                risk_level="dangerous",
                approval_policy="approval_required",
            ),
        ),
        handler=terminate_task,
    )
    registry.register(
        CapabilityDefinition(
            "tasks.priority.set",
            "tasks",
            "runtime_action",
            True,
            SUPPORTED_PROVIDERS,
            manual_control=_manual(
                label="调整任务优先级",
                description="调整指定任务的治理优先级",
                risk_level="operate",
            ),
        ),
        handler=set_task_priority,
    )
    registry.register(
        CapabilityDefinition(
            "scheduler.budget.configure",
            "scheduler",
            "runtime_action",
            False,
            SUPPORTED_PROVIDERS,
            manual_control=_manual(
                label="配置功率预算",
                description="调整总功率预算治理参数",
                risk_level="operate",
            ),
        ),
        handler=configure_budget,
    )
    registry.register(
        CapabilityDefinition(
            "scheduler.run_once",
            "scheduler",
            "runtime_action",
            False,
            SUPPORTED_PROVIDERS,
            manual_control=_manual(
                label="执行一次调度",
                description="手动触发一次完整调度",
                risk_level="control",
                approval_policy="confirm_required",
            ),
        ),
        handler=run_schedule_once_capability,
    )
    registry.register(
        CapabilityDefinition(
            "job.submit",
            "jobs",
            "runtime_action",
            False,
            SUPPORTED_PROVIDERS,
            manual_control=_manual(
                label="提交作业",
                description="向当前集群提交一条作业",
                risk_level="control",
            ),
        ),
        handler=submit_job,
    )
    registry.register(
        CapabilityDefinition(
            "job.list",
            "jobs",
            "observe",
            False,
            SUPPORTED_PROVIDERS,
            manual_control=_manual(
                label="查看作业列表",
                description="查看当前工作区内的作业列表",
                required_role="observer",
            ),
        ),
        handler=list_jobs,
    )
    registry.register(
        CapabilityDefinition(
            "job.get",
            "jobs",
            "observe",
            False,
            SUPPORTED_PROVIDERS,
            manual_control=_manual(
                label="查看作业详情",
                description="查看指定作业详情",
                required_role="observer",
            ),
        ),
        handler=get_job,
    )
    registry.register(
        CapabilityDefinition(
            "job.pause",
            "jobs",
            "runtime_action",
            False,
            SUPPORTED_PROVIDERS,
            manual_control=_manual(
                label="暂停作业",
                description="暂停指定作业",
                required_role="admin",
                risk_level="dangerous",
                approval_policy="approval_required",
                enabled=False,
            ),
        ),
        handler=pause_job,
    )
    registry.register(
        CapabilityDefinition(
            "job.resume",
            "jobs",
            "runtime_action",
            False,
            SUPPORTED_PROVIDERS,
            manual_control=_manual(
                label="恢复作业",
                description="恢复指定作业",
                required_role="admin",
                risk_level="dangerous",
                approval_policy="approval_required",
                enabled=False,
            ),
        ),
        handler=resume_job,
    )
    registry.register(
        CapabilityDefinition(
            "job.cancel",
            "jobs",
            "runtime_action",
            False,
            SUPPORTED_PROVIDERS,
            manual_control=_manual(
                label="取消作业",
                description="取消指定作业",
                required_role="admin",
                risk_level="dangerous",
                approval_policy="approval_required",
                enabled=False,
            ),
        ),
        handler=cancel_job,
    )
    registry.register(
        CapabilityDefinition(
            "queue.status.read",
            "queues",
            "observe",
            False,
            SUPPORTED_PROVIDERS,
            manual_control=_manual(
                label="查看队列状态",
                description="查看当前集群的队列状态",
                required_role="observer",
            ),
        ),
        handler=queue_status_read,
    )
    return registry
