import os
import sys

import pytest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.goal_runtime.capability import CapabilityDefinition  # noqa: E402
from app.services.goal_runtime.capability_registry import CapabilityRegistry  # noqa: E402
from app.services.goal_runtime.permission_policy import requires_approval  # noqa: E402
from app.services.goal_runtime.platform_capabilities import (  # noqa: E402
    build_platform_capability_registry,
)


class FakeAgent:
    async def get_all_gpus(self):
        return [{"index": 0, "name": "GPU 0"}]

    async def get_processes(self):
        return [{"pid": 12, "gpu_index": 0}]

    async def set_power_limit(self, gpu_index, power_limit):
        return {"success": True, "gpu_index": gpu_index, "power_limit": power_limit}

    async def pause_task(self, pid):
        return {"success": True, "pid": pid}

    async def resume_task(self, pid):
        return {"success": True, "pid": pid}

    async def terminate_task(self, pid):
        return {"success": True, "pid": pid}


class FakeImportContext:
    def filter_gpus(self, gpus):
        return gpus

    def filter_processes(self, processes):
        return processes

    def ensure_gpu_allowed(self, gpu_index):
        return gpu_index

    def ensure_process_allowed(self, pid, processes):
        return pid


class FakeScheduler:
    def __init__(self):
        self.cleared_gpu_indexes = []
        self.configured_budget = None

    def clear_managed_gpu(self, gpu_index):
        self.cleared_gpu_indexes.append(gpu_index)

    def configure_budget(self, enabled, total_power_budget):
        self.configured_budget = (enabled, total_power_budget)

    def get_budget_status(self, gpus):
        return {"enabled": False, "gpu_count": len(gpus)}


class FakeStore:
    async def set_task_priority(self, pid, priority):
        return {"pid": pid, "priority": priority}


class FakeAppState:
    def __init__(self):
        self.agent = FakeAgent()
        self.import_context = FakeImportContext()
        self.scheduler = FakeScheduler()
        self.store = FakeStore()


def test_permission_policy_only_requires_approval_for_runtime_actions_in_low_mode():
    read_cap = CapabilityDefinition(
        "runtime.snapshot.read",
        "runtime",
        "observe",
        False,
        ("http_local",),
    )
    act_cap = CapabilityDefinition(
        "tasks.pause",
        "tasks",
        "runtime_action",
        True,
        ("http_local",),
    )

    assert requires_approval(read_cap, "low") is False
    assert requires_approval(act_cap, "low") is True
    assert requires_approval(act_cap, "high") is False


def test_capability_registry_returns_registered_definition():
    registry = CapabilityRegistry()
    definition = CapabilityDefinition(
        "tasks.pause",
        "tasks",
        "runtime_action",
        True,
        ("http_local",),
    )

    registry.register(definition, handler=lambda ctx, args: {"success": True})
    selected = registry.get("tasks.pause")

    assert selected.definition.name == "tasks.pause"
    assert callable(selected.handler)


def test_capability_registry_raises_on_missing_capability():
    registry = CapabilityRegistry()

    with pytest.raises(KeyError):
        registry.get("missing.capability")


def test_runtime_action_capability_declares_scope_and_provider_support():
    registry = build_platform_capability_registry(FakeAppState())
    pause = registry.get("tasks.pause").definition
    snapshot = registry.get("runtime.snapshot.read").definition

    assert pause.requires_scope is True
    assert "ssh_linux" in pause.supported_providers
    assert snapshot.requires_scope is False
