from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
CLUSTER_VIEW_PATH = ROOT / "frontend" / "src" / "views" / "ClusterJobs.vue"
CLUSTER_ACTIONS_PATH = ROOT / "frontend" / "src" / "lib" / "clusterConsoleActions.js"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.cluster_control.models import JobSpecRecord
from app.services.cluster_control.reconcile_controller import ClusterReconcileController
from app.services.cluster_control.scheduler_core import ClusterSchedulerCore


DEFAULT_QUEUE_ID = "queue-main"
DEFAULT_MEMORY_BYTES = 32 * 1024 * 1024 * 1024
MEDIUM_MEMORY_BYTES = 16 * 1024 * 1024 * 1024
SMALL_MEMORY_BYTES = 8 * 1024 * 1024 * 1024

PLAN_TONES = {
    "place": "green",
    "wait": "amber",
    "reject": "red",
    "hold": "slate",
    "preempt_then_place": "blue",
}
OBJECT_LABELS = {
    "job": "作业对象",
    "queue": "队列对象",
    "node": "节点对象",
    "allocation": "allocation 对象",
}
OBJECT_ORDER = ("job", "queue", "node", "allocation")


def build_cluster_governance_dataset() -> dict:
    return {
        "decision_matrix": build_decision_matrix(),
        "reconcile_flow": build_reconcile_flow(),
        "governance_coverage": build_governance_coverage(),
    }


def build_decision_matrix() -> list[dict]:
    core = ClusterSchedulerCore()
    return [
        _serialize_decision(
            core.plan_job(_job("job-place"), _place_nodes(), queue=_active_queue()),
            condition="队列 active，node-a/ node-b 都可调度，node-a 资源贴合度更高。",
            meaning="证明调度器会先做准入与资源匹配，再按 best-fit 选择放置节点。",
        ),
        _serialize_decision(
            core.plan_job(
                _job("job-wait", queue_id="queue-busy"),
                _place_nodes(),
                queue=_active_queue(queue_id="queue-busy", max_concurrency=1),
                jobs=[_running_job("job-running", queue_id="queue-busy")],
            ),
            condition="队列仍是 active，但同队列运行作业已达到 max_concurrency=1。",
            meaning="证明系统不会盲目继续放置，而是把作业留在等待态，避免抢占式超发。",
        ),
        _serialize_decision(
            core.plan_job(
                _job("job-reject", queue_id="queue-paused"),
                _place_nodes(),
                queue={"queue_id": "queue-paused", "state": "paused", "max_concurrency": 0},
            ),
            condition="队列被运维切为 paused，作业在准入层直接被拒绝。",
            meaning="证明治理状态能在调度入口生效，队列停用后不会再进入资源竞争。",
        ),
        _serialize_decision(
            core.plan_job(
                _job("job-hold", priority=95),
                [_blocked_node()],
                queue=_active_queue(),
                jobs=[_running_job("job-protected", priority=90, preemptible=False)],
                allocations=[_allocation("alloc-protected", "job-protected", "node-blocked")],
            ),
            condition="节点上已有占用，但现有作业不可抢占，调度器只能等待可回收对象出现。",
            meaning="证明系统不会把“不可治理”的占用伪装成可执行计划，而是明确输出 hold。",
        ),
        _serialize_decision(
            core.plan_job(
                _job("job-preempt", priority=100),
                [_preemptible_blocked_node()],
                queue=_active_queue(),
                jobs=[_running_job("job-low-priority", priority=20, preemptible=True)],
                allocations=[_allocation("alloc-low-priority", "job-low-priority", "node-blocked")],
            ),
            condition="目标作业优先级更高，节点被低优先级可抢占作业占用。",
            meaning="证明调度器会输出“先抢占再放置”的治理计划，而不是只给静态告警。",
        ),
    ]


def build_reconcile_flow() -> dict:
    return asyncio.run(_capture_reconcile_flow())


def build_governance_coverage() -> list[dict]:
    grouped = {name: [] for name in OBJECT_ORDER}
    for capability in _cluster_capabilities():
        object_name, _, action = capability.partition(".")
        if object_name not in grouped:
            continue
        grouped[object_name].append(action)
    return [
        _coverage_item(object_name, grouped[object_name])
        for object_name in OBJECT_ORDER
        if grouped[object_name]
    ]


def _serialize_decision(plan, *, condition: str, meaning: str) -> dict:
    return {
        "plan_type": plan.plan_type,
        "condition": condition,
        "meaning": meaning,
        "reason": plan.reason,
        "selected_node": plan.selected_node or "无",
        "selected_devices": list(plan.selected_devices),
        "victim_job_ids": list(plan.victim_job_ids),
        "required_actions": [dict(item) for item in plan.required_actions],
        "tone": PLAN_TONES.get(plan.plan_type, "slate"),
    }


def _job(
    job_id: str,
    *,
    queue_id: str = DEFAULT_QUEUE_ID,
    priority: int = 80,
    preemptible: bool = True,
) -> JobSpecRecord:
    return JobSpecRecord(
        job_id=job_id,
        tenant_id="tenant-a",
        project_id="project-governance",
        queue_id=queue_id,
        submitter_id="analyst",
        job_type="batch",
        entrypoint="python train.py",
        args=(),
        env={},
        resource_request={"gpu": 1, "cpu": 8, "memory_bytes": DEFAULT_MEMORY_BYTES},
        placement_constraints={},
        priority=priority,
        preemptible=preemptible,
        max_retries=0,
        timeout_seconds=0,
        runtime_profile={},
    )


def _running_job(
    job_id: str,
    *,
    queue_id: str = DEFAULT_QUEUE_ID,
    priority: int = 50,
    preemptible: bool = True,
) -> dict:
    return {
        "job_id": job_id,
        "queue_id": queue_id,
        "status": "running",
        "priority": priority,
        "preemptible": preemptible,
        "submitter_id": "tenant-user",
        "lifecycle_kind": "batch",
        "task_kind": "batch_compute",
        "runtime_profile": {"restartable": True},
        "resource_request": {"gpu": 1, "cpu": 8, "memory_bytes": MEDIUM_MEMORY_BYTES},
    }


def _allocation(allocation_id: str, job_id: str, node_id: str) -> dict:
    return {
        "allocation_id": allocation_id,
        "job_id": job_id,
        "node_id": node_id,
        "status": "active",
        "gpu_bindings": ("gpu-0",),
    }


def _active_queue(*, queue_id: str = DEFAULT_QUEUE_ID, max_concurrency: int = 0) -> dict:
    return {"queue_id": queue_id, "state": "active", "max_concurrency": max_concurrency}


def _place_nodes() -> list[dict]:
    return [
        {
            "node_id": "node-a",
            "schedulable": True,
            "drain_state": "active",
            "gpu_free": 1,
            "cpu_free": 8,
            "memory_bytes_free": DEFAULT_MEMORY_BYTES,
            "device_ids": ("gpu-0",),
            "execution_backend": "http_agent",
        },
        {
            "node_id": "node-b",
            "schedulable": True,
            "drain_state": "active",
            "gpu_free": 4,
            "cpu_free": 64,
            "memory_bytes_free": DEFAULT_MEMORY_BYTES * 2,
            "device_ids": ("gpu-0", "gpu-1", "gpu-2", "gpu-3"),
            "execution_backend": "http_agent",
        },
    ]


def _blocked_node() -> dict:
    return {
        "node_id": "node-blocked",
        "schedulable": True,
        "drain_state": "active",
        "gpu_free": 0,
        "cpu_free": 8,
        "memory_bytes_free": SMALL_MEMORY_BYTES,
        "device_ids": ("gpu-0",),
        "execution_backend": "http_agent",
    }


def _preemptible_blocked_node() -> dict:
    node = _blocked_node()
    node["memory_bytes_free"] = MEDIUM_MEMORY_BYTES
    return node


async def _capture_reconcile_flow() -> dict:
    manual = await _manual_reconcile_run()
    skipped = await _skipped_reconcile_run()
    return {"manual_run": manual, "skip_run": skipped}


async def _manual_reconcile_run() -> dict:
    async def runtime_status_reader():
        return {"status": "connected"}

    async def nodes_loader():
        return [{"node_id": "node-a"}, {"node_id": "node-b"}]

    async def reconcile_runner(nodes):
        return {"placed": len(nodes), "preempted": 1, "restored": 1, "released": 1}

    controller = ClusterReconcileController(
        nodes_loader=nodes_loader,
        reconcile_runner=reconcile_runner,
        runtime_status_reader=runtime_status_reader,
        enabled=False,
    )
    before = controller.snapshot()
    summary = await controller.run_once(trigger="manual")
    after = controller.snapshot()
    return _serialize_reconcile_case(before, after, summary, "一次人工调和会形成可回写的状态摘要。")


async def _skipped_reconcile_run() -> dict:
    async def runtime_status_reader():
        return {"status": "reconnecting"}

    async def nodes_loader():
        return [{"node_id": "node-a"}]

    async def reconcile_runner(_nodes):
        return {"placed": 99}

    controller = ClusterReconcileController(
        nodes_loader=nodes_loader,
        reconcile_runner=reconcile_runner,
        runtime_status_reader=runtime_status_reader,
        enabled=False,
    )
    before = controller.snapshot()
    summary = await controller.run_once(trigger="background")
    after = controller.snapshot()
    return _serialize_reconcile_case(before, after, summary, "运行时未连通时会显式跳过，不会伪造治理成功。")


def _serialize_reconcile_case(before: dict, after: dict, summary: dict, meaning: str) -> dict:
    return {
        "trigger": after["last_trigger"],
        "runtime_status": summary.get("runtime_status", "unknown"),
        "tick_count_delta": after["tick_count"] - before["tick_count"],
        "skipped": bool(summary.get("skipped", False)),
        "skip_reason": summary.get("skip_reason", ""),
        "summary": {key: value for key, value in summary.items() if key not in {"skipped", "runtime_status", "skip_reason"}},
        "last_summary_keys": sorted(after["last_summary"].keys()),
        "meaning": meaning,
    }


def _cluster_capabilities() -> list[str]:
    pattern = re.compile(r"'((?:job|queue|node|allocation)\.[a-z_]+)'")
    texts = (
        CLUSTER_VIEW_PATH.read_text(encoding="utf-8"),
        CLUSTER_ACTIONS_PATH.read_text(encoding="utf-8"),
    )
    names = sorted({match for text in texts for match in pattern.findall(text)})
    return names


def _coverage_item(object_name: str, actions: list[str]) -> dict:
    evidence = {
        "job": "作业台账提交与行内动作，共享 submitBuiltinCommand 与刷新回写。",
        "queue": "队列对象通过 queue.reconcile 进入调和控制器，状态回写到 controller snapshot。",
        "node": "节点对象通过 drain_state 在调和前改变可调度性，再刷新节点快照。",
        "allocation": "allocation.release 先释放资源，再触发作业状态回摆，避免资源悬挂。",
    }
    surface = {
        "job": "ClusterJobLedger 提交区 + 行内动作",
        "queue": "ClusterConsoleToolbar 手动调和",
        "node": "ClusterAllocationPanel 节点排空切换",
        "allocation": "ClusterAllocationPanel allocation 释放",
    }
    return {
        "object": object_name,
        "label": OBJECT_LABELS[object_name],
        "actions": sorted(actions),
        "action_count": len(actions),
        "surface": surface[object_name],
        "evidence": evidence[object_name],
    }
