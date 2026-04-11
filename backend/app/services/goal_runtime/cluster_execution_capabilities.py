from __future__ import annotations

from app.services.goal_runtime.capability import CapabilityDefinition


def register_cluster_execution_capabilities(
    registry,
    app_state,
    *,
    supported_providers: tuple[str, ...],
    manual_factory,
) -> None:
    async def reconcile_queue(_context, _arguments):
        controller = getattr(app_state, "cluster_reconcile_controller", None)
        if controller is None:
            raise RuntimeError("cluster reconcile controller unavailable")
        return await controller.run_once(trigger="manual")

    async def requeue_job(_context, arguments):
        return await app_state.cluster_control.requeue_job(str(arguments["job_id"]))

    async def preempt_job(_context, arguments):
        return await app_state.cluster_control.preempt_job(str(arguments["job_id"]))

    async def checkpoint_job(_context, arguments):
        return await app_state.cluster_control.checkpoint_job(
            str(arguments["job_id"]),
            timeout_seconds=int(arguments.get("timeout_seconds") or 30),
        )

    async def restore_job(_context, arguments):
        return await app_state.cluster_control.restore_job(
            str(arguments["job_id"]),
            checkpoint_id=str(arguments.get("checkpoint_id") or ""),
        )

    registry.register(
        CapabilityDefinition(
            "queue.reconcile",
            "queues",
            "runtime_action",
            False,
            supported_providers,
            manual_control=manual_factory(
                label="执行队列调和",
                description="重新评估 queued/pending 作业并尝试实际分发",
                risk_level="control",
                approval_policy="confirm_required",
            ),
        ),
        handler=reconcile_queue,
    )
    registry.register(
        CapabilityDefinition(
            "job.requeue",
            "jobs",
            "runtime_action",
            False,
            supported_providers,
            manual_control=manual_factory(
                label="重新入队作业",
                description="将批处理作业转回等待队列，并触发资源回收",
                risk_level="control",
                approval_policy="confirm_required",
            ),
        ),
        handler=requeue_job,
    )
    registry.register(
        CapabilityDefinition(
            "job.preempt",
            "jobs",
            "runtime_action",
            False,
            supported_providers,
            manual_control=manual_factory(
                label="抢占作业",
                description="将可回收的批处理作业置为 preempting 并释放资源",
                risk_level="control",
                approval_policy="confirm_required",
            ),
        ),
        handler=preempt_job,
    )
    registry.register(
        CapabilityDefinition(
            "job.checkpoint",
            "jobs",
            "runtime_action",
            False,
            supported_providers,
            manual_control=manual_factory(
                label="创建检查点",
                description="为支持 app_managed 的作业发起检查点请求",
                risk_level="control",
                approval_policy="confirm_required",
            ),
        ),
        handler=checkpoint_job,
    )
    registry.register(
        CapabilityDefinition(
            "job.restore",
            "jobs",
            "runtime_action",
            False,
            supported_providers,
            manual_control=manual_factory(
                label="恢复作业",
                description="基于最近一次就绪检查点恢复作业",
                risk_level="control",
                approval_policy="confirm_required",
            ),
        ),
        handler=restore_job,
    )
