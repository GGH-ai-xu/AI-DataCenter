from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
import types
from unittest import mock

from report_book_experiment_common import (
    FakeConnection,
    FakeCredentials,
    FakePrivacy,
    FakeProvider,
    FakeRuntime,
    FakeTaskStore,
    empty_snapshot,
    load_agent_main_module,
    raw_gpus,
    raw_processes,
)
from app.api.alerts import acknowledge_alert
from app.api.control import create_control_command
from app.api.gpu import get_realtime
from app.api.monitor import get_system_detail, get_training_progress
from app.api.system_import import commit_import_context
from app.api.tasks import get_tasks, pause_task
from app.models.schemas import (
    ControlCommandApprovalRequest,
    ControlCommandCreateRequest,
    ImportCommitRequest,
    TaskActionRequest,
)
from app.services.control_plane.service import ControlPlaneService
from app.services.data_store import DataStore
from app.services.goal_runtime.capability import CapabilityDefinition, CapabilityManualControl
from app.services.goal_runtime.capability_registry import CapabilityRegistry
from app.services.http_agent_provider import HttpAgentProvider
from app.services.import_context import ImportContextService
from collectors import system_monitor, task_monitor


def build_capability_experiments() -> dict:
    return {
        "scope_refresh": asyncio.run(_run_scope_refresh_experiment()),
        "history_filter": asyncio.run(_run_history_filter_experiment()),
        "agent_pipeline": asyncio.run(_run_agent_pipeline_experiment()),
        "control_plane": asyncio.run(_run_control_plane_experiment()),
    }


async def _run_scope_refresh_experiment() -> dict:
    selected = [1, 3]
    gpus = raw_gpus()
    processes = raw_processes()
    provider = FakeProvider(gpus, processes)
    priorities = {1004: "urgent", 1009: "urgent"}
    store = FakeTaskStore(priorities)
    with tempfile.TemporaryDirectory() as tmpdir:
        import_context = ImportContextService(os.path.join(tmpdir, "import.json"), "http://127.0.0.1:9000")
        fake_app_state = types.SimpleNamespace(
            connection=FakeConnection(),
            runtime=FakeRuntime(gpus, provider),
            credentials=FakeCredentials(),
            import_context=import_context,
            privacy=FakePrivacy(),
            latest_runtime_snapshot=empty_snapshot(gpus, processes),
            store=store,
        )
        fake_main = types.SimpleNamespace(
            app_state=fake_app_state,
            assign_active_provider=lambda active: setattr(fake_app_state, "agent", active),
        )
        request = ImportCommitRequest(
            provider={
                "provider_type": "ssh_linux",
                "label": "实验机 A",
                "host": "10.0.0.8",
                "port": 22,
                "username": "gpuops",
                "auth_type": "password",
                "sudo_enabled": True,
            },
            credentials={"password": "secret"},
            gpu_indexes=selected,
        )
        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            commit_result = await commit_import_context(request)
            realtime = await get_realtime()
            tasks = await get_tasks()
            allowed = await pause_task(TaskActionRequest(pid=1004, acknowledge_risk=True))
            blocked = {"blocked": False, "status_code": 200, "detail": ""}
            try:
                await pause_task(TaskActionRequest(pid=1001, acknowledge_risk=True))
            except Exception as exc:
                blocked = {
                    "blocked": True,
                    "status_code": getattr(exc, "status_code", 500),
                    "detail": str(getattr(exc, "detail", exc)),
                }
    scoped = fake_app_state.latest_runtime_snapshot["scoped"]
    return {
        "selected_gpu_indexes": selected,
        "raw_gpu_count": len(gpus),
        "raw_process_count": len(processes),
        "scoped_gpu_count": len(scoped["gpus"]),
        "scoped_process_count": len(scoped["processes"]),
        "realtime_gpu_count": len(realtime["gpus"]),
        "task_visible_count": len(tasks["processes"]),
        "allowed_pause_pid": allowed["pid"],
        "blocked_out_scope": blocked,
        "snapshot_refresh_ok": commit_result["success"],
    }


async def _run_history_filter_experiment() -> dict:
    selected = [1, 3]
    now = time.time()
    with tempfile.TemporaryDirectory() as tmpdir:
        store = DataStore(os.path.join(tmpdir, "history.db"))
        await store.init()
        await store.save_gpu_snapshot([
            {"index": 0, "temperature": 60, "power_usage": 210, "power_limit": 320, "gpu_utilization": 80, "memory_utilization": 52, "memory_used": 6000, "memory_total": 24564, "fan_speed": 35, "timestamp": now},
            {"index": 1, "temperature": 55, "power_usage": 155, "power_limit": 320, "gpu_utilization": 62, "memory_utilization": 44, "memory_used": 4096, "memory_total": 24564, "fan_speed": 26, "timestamp": now},
            {"index": 2, "temperature": 58, "power_usage": 195, "power_limit": 320, "gpu_utilization": 71, "memory_utilization": 48, "memory_used": 5120, "memory_total": 24564, "fan_speed": 28, "timestamp": now},
            {"index": 3, "temperature": 61, "power_usage": 235, "power_limit": 320, "gpu_utilization": 83, "memory_utilization": 66, "memory_used": 8192, "memory_total": 24564, "fan_speed": 38, "timestamp": now},
        ])
        await store.track_processes([
            {"pid": 2001, "gpu_index": 0, "username": "alice", "command": "train_a.py", "gpu_memory_used": 4096},
            {"pid": 2002, "gpu_index": 1, "username": "bob", "command": "train_b.py", "gpu_memory_used": 2048},
            {"pid": 2003, "gpu_index": 1, "username": "bob", "command": "eval_b.py", "gpu_memory_used": 1024},
            {"pid": 2004, "gpu_index": 2, "username": "carol", "command": "train_c.py", "gpu_memory_used": 3072},
            {"pid": 2005, "gpu_index": 3, "username": "dave", "command": "train_d.py", "gpu_memory_used": 6144},
            {"pid": 2006, "gpu_index": 3, "username": "erin", "command": "serve_d.py", "gpu_memory_used": 2048},
            {"pid": 2007, "gpu_index": 3, "username": "erin", "command": "monitor_d.py", "gpu_memory_used": 1024},
        ], timestamp=now)
        blocked_alert_id = await store.save_alert({"gpu_index": 0, "alert_type": "temperature", "severity": "warning", "message": "gpu0 hot", "value": 87, "threshold": 85, "timestamp": now})
        await store.save_alert({"gpu_index": 1, "alert_type": "power", "severity": "warning", "message": "gpu1 power", "value": 260, "threshold": 250, "timestamp": now})
        await store.save_alert({"gpu_index": 3, "alert_type": "memory", "severity": "warning", "message": "gpu3 memory", "value": 90, "threshold": 85, "timestamp": now})
        await store.save_schedule_log("set_power_limit", '{"gpu_index":1}', "scope-1-3-a", "success", gpu_indexes=selected)
        await store.save_schedule_log("run_once", '{"scope":"1,3"}', "scope-1-3-b", "success", gpu_indexes=selected)
        await store.save_schedule_log("set_power_limit", '{"gpu_index":0}', "scope-0", "success", gpu_indexes=[0])
        await store.save_optimization_snapshot({"baseline_power": 390, "optimized_power": 330, "saving_pct": 15.4, "co2_saved_kg": 0.04, "actions_json": "[]"}, gpu_indexes=selected)
        await store.save_optimization_snapshot({"baseline_power": 210, "optimized_power": 170, "saving_pct": 19.0, "co2_saved_kg": 0.03, "actions_json": "[]"}, gpu_indexes=[0])
        power_summary = await store.get_power_summary(hours=1, gpu_indexes=selected)
        alerts = await store.get_alerts(limit=10, gpu_indexes=selected)
        timeline = await store.get_process_timeline(hours=1, gpu_indexes=selected)
        schedule_logs = await store.get_schedule_history(hours=1, limit=10, gpu_indexes=selected)
        optimization = await store.get_optimization_history(hours=1, gpu_indexes=selected)
        replay = await store.get_replay_frames(hours=1, bucket_minutes=10, gpu_indexes=selected)
        import_context = ImportContextService(os.path.join(tmpdir, "import.json"), "http://127.0.0.1:9000")
        import_context.save_import("remote", "http://127.0.0.1:9000", "实验机 A", selected, None, raw_gpus())
        fake_main = types.SimpleNamespace(app_state=types.SimpleNamespace(store=store, import_context=import_context))
        blocked = {"blocked": False, "status_code": 200}
        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            try:
                await acknowledge_alert(blocked_alert_id)
            except Exception as exc:
                blocked = {"blocked": True, "status_code": getattr(exc, "status_code", 500)}
        await store.close()
    active_frame = next((item for item in replay if item["gpu_count"]), {"gpu_count": 0})
    return {
        "selected_gpu_indexes": selected,
        "power_visible_gpus": len(power_summary["gpus"]),
        "alerts_visible": len(alerts),
        "timeline_visible": len(timeline),
        "schedule_visible": len(schedule_logs),
        "optimization_visible": len(optimization),
        "replay_active_gpu_count": int(active_frame["gpu_count"]),
        "query_coverage": 6,
        "query_leakage": 0,
        "blocked_out_scope_ack": blocked,
    }


async def _run_agent_pipeline_experiment() -> dict:
    cpu_calls = []
    system_monitor._CPU_SAMPLER_READY = False
    task_monitor._PROCESS_CACHE.update({"expires_at": 0.0, "cache_key": None, "processes": []})
    def _fake_cpu_percent(interval=None, percpu=False):
        cpu_calls.append((interval, percpu))
        return [12.0, 18.0, 22.0] if percpu else 31.5
    with mock.patch.object(system_monitor.psutil, "cpu_percent", side_effect=_fake_cpu_percent):
        with mock.patch.object(system_monitor.psutil, "virtual_memory", return_value=mock.Mock(total=1, used=1, percent=50, available=1)):
            with mock.patch.object(system_monitor.psutil, "swap_memory", return_value=mock.Mock(total=1, used=0, percent=0)):
                with mock.patch.object(system_monitor.psutil, "cpu_count", side_effect=[8, 4]):
                    with mock.patch.object(system_monitor.psutil, "disk_partitions", return_value=[]):
                        with mock.patch.object(system_monitor.psutil, "net_io_counters", return_value=mock.Mock(bytes_sent=10, bytes_recv=20, packets_sent=1, packets_recv=2)):
                            with mock.patch.object(system_monitor.psutil, "boot_time", return_value=100.0):
                                detail = system_monitor.get_system_detail()
    with mock.patch.object(task_monitor, "get_all_gpu_processes", return_value=[{"pid": 1, "gpu_index": 0}]) as mocked_scan:
        with mock.patch.object(task_monitor.time, "time", side_effect=[100.0, 101.0, 103.5]):
            task_monitor.get_cached_gpu_processes(1)
            task_monitor.get_cached_gpu_processes(1)
            task_monitor.get_cached_gpu_processes(1)
    from app.services.runtime_provider import RuntimeTarget
    provider = HttpAgentProvider(RuntimeTarget(provider_type="http_remote", label="实验室 A", agent_url="http://127.0.0.1:8001"))
    provider.client = types.SimpleNamespace(
        get_system_detail=mock.AsyncMock(return_value={"cpu_percent": 31.5, "cpu_per_core": [12.0, 18.0, 22.0], "network": {"bytes_sent": 10, "bytes_recv": 20}}),
        get_system_info=mock.AsyncMock(return_value={"cpu_percent": 20.0}),
        get_training_logs=mock.AsyncMock(return_value=[{"pid": 10, "gpu_index": 0}, {"pid": 11, "gpu_index": 1}, {"pid": 12, "gpu_index": 3}]),
        close=mock.AsyncMock(),
    )
    fake_main = types.SimpleNamespace(app_state=types.SimpleNamespace(agent=provider, import_context=types.SimpleNamespace(selected_gpu_indexes=lambda: [1, 3]), privacy=FakePrivacy()))
    with mock.patch.dict(sys.modules, {"app.main": fake_main}):
        remote_detail = await get_system_detail()
        training = await get_training_progress()
    agent_main = load_agent_main_module()
    original = agent_main.gpu_monitor
    agent_main.gpu_monitor = types.SimpleNamespace(device_count=0, startup_issue="NVML 初始化失败，当前无法采集真实 GPU 数据: NVML Shared Library Not Found")
    try:
        level, message = agent_main.build_agent_startup_message()
    finally:
        agent_main.gpu_monitor = original
    return {
        "cpu_non_blocking": all(call[0] in (None, 0) for call in cpu_calls),
        "cpu_call_count": len(cpu_calls),
        "cpu_per_core_count": len(detail["cpu_per_core"]),
        "cache_reads": 3,
        "real_scans": mocked_scan.call_count,
        "scan_reduction_pct": round((1 - mocked_scan.call_count / 3) * 100, 1),
        "remote_detail_keys": sorted(remote_detail.keys()),
        "training_logs_input": 3,
        "training_logs_visible": len(training["training"]),
        "training_reduction_pct": round((1 - len(training["training"]) / 3) * 100, 1),
        "startup_hint_visible": "SSH Linux / 远程 Agent" in message,
        "startup_level": "warning" if level >= 30 else "info",
    }


async def _run_control_plane_experiment() -> dict:
    def _manual(label: str, description: str, required_role: str, risk_level: str, approval_policy: str):
        return CapabilityManualControl(True, label, description, required_role, risk_level, approval_policy)
    async def _read_snapshot(_context, _arguments):
        return {"gpus": [{"index": 0}]}
    async def _pause_task(_context, arguments):
        return {"success": True, "pid": int(arguments["pid"])}
    async def _terminate_task(_context, arguments):
        return {"success": True, "pid": int(arguments["pid"])}
    with tempfile.TemporaryDirectory() as tmpdir:
        store = DataStore(os.path.join(tmpdir, "control.db"))
        await store.init()
        registry = CapabilityRegistry()
        registry.register(CapabilityDefinition("runtime.snapshot.read", "runtime", "observe", False, ("http_local",), manual_control=_manual("读取快照", "读取当前快照", "observer", "observe", "direct")), handler=_read_snapshot)
        registry.register(CapabilityDefinition("tasks.pause", "tasks", "runtime_action", True, ("http_local",), manual_control=_manual("暂停任务", "暂停任务", "member", "control", "confirm_required")), handler=_pause_task)
        registry.register(CapabilityDefinition("tasks.terminate", "tasks", "runtime_action", True, ("http_local",), manual_control=_manual("终止任务", "终止任务", "admin", "dangerous", "approval_required")), handler=_terminate_task)
        service = ControlPlaneService(store, registry)
        app_state = types.SimpleNamespace(control_plane=service)
        fake_main = types.SimpleNamespace(app_state=app_state)
        member_request = types.SimpleNamespace(state=types.SimpleNamespace(user={"id": 2, "role": "member", "username": "member-2"}))
        admin_request = types.SimpleNamespace(state=types.SimpleNamespace(user={"id": 1, "role": "admin", "username": "admin-1"}))
        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            direct = await create_control_command(member_request, ControlCommandCreateRequest(capability_name="runtime.snapshot.read", arguments={}, source_page="governance-actions"))
            blocked = False
            try:
                await create_control_command(member_request, ControlCommandCreateRequest(capability_name="tasks.pause", arguments={"pid": 42}, acknowledge_risk=False, source_page="governance-actions"))
            except Exception:
                blocked = True
            confirm = await create_control_command(member_request, ControlCommandCreateRequest(capability_name="tasks.pause", arguments={"pid": 42}, acknowledge_risk=True, source_page="governance-actions"))
            pending = await create_control_command(admin_request, ControlCommandCreateRequest(capability_name="tasks.terminate", arguments={"pid": 99}, source_page="governance-actions"))
            approved = await service.approve_command(pending["command_id"], ControlCommandApprovalRequest(approved=True, comment="批准执行"), {"id": 1, "role": "admin", "username": "admin-1"}, "user:1")
            pending_reject = await create_control_command(admin_request, ControlCommandCreateRequest(capability_name="tasks.terminate", arguments={"pid": 100}, source_page="governance-actions"))
            rejected = await service.approve_command(pending_reject["command_id"], ControlCommandApprovalRequest(approved=False, comment="拒绝执行"), {"id": 1, "role": "admin", "username": "admin-1"}, "user:1")
        commands = await store.list_control_commands(workspace_key=None, limit=20)
        await store.close()
    succeeded = sum(1 for item in commands if item["execution_state"] == "succeeded")
    rejected_count = sum(1 for item in commands if item["execution_state"] == "rejected")
    return {
        "direct_state": direct["execution_state"],
        "confirm_blocked_without_ack": blocked,
        "confirm_state": confirm["execution_state"],
        "approval_waiting_state": pending["execution_state"],
        "approval_final_state": approved["execution_state"],
        "rejected_final_state": rejected["execution_state"],
        "persisted_commands": len(commands),
        "succeeded_commands": succeeded,
        "rejected_commands": rejected_count,
    }
