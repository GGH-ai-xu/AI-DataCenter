import os
import sys
import types
import unittest

import pytest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.goal_runtime.capability import CapabilityDefinition  # noqa: E402
from app.services.goal_runtime.capability_registry import CapabilityRegistry  # noqa: E402
from app.services.goal_runtime.executor import execute_capability  # noqa: E402
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
        self.auto_enabled = False
        self.carbon_budget = None

    def clear_managed_gpu(self, gpu_index):
        self.cleared_gpu_indexes.append(gpu_index)

    def configure_budget(self, enabled, total_power_budget):
        self.configured_budget = (enabled, total_power_budget)

    def set_auto(self, enabled):
        self.auto_enabled = bool(enabled)

    def configure_carbon_budget(self, enabled, daily_kg):
        self.carbon_budget = (bool(enabled), float(daily_kg))

    def get_budget_status(self, gpus):
        return {"enabled": False, "gpu_count": len(gpus)}

    def get_carbon_budget_status(self, gpus):
        enabled, daily_kg = self.carbon_budget or (False, 50.0)
        return {
            "enabled": enabled,
            "daily_budget_kg": daily_kg,
            "gpu_count": len(gpus),
        }


class FakeStore:
    def __init__(self):
        self.jobs = {}
        self.nodes = {}
        self.rules = {}

    async def set_task_priority(self, pid, priority):
        return {"pid": pid, "priority": priority}

    async def create_cluster_job(self, record):
        self.jobs[record.job_id] = {
            "job_id": record.job_id,
            "queue_id": record.queue_id,
            "tenant_id": record.tenant_id,
            "project_id": record.project_id,
            "submitter_id": record.submitter_id,
            "job_type": record.job_type,
            "entrypoint": record.entrypoint,
            "resource_request": dict(record.resource_request),
            "task_kind": str(getattr(record, "task_kind", "")),
            "lifecycle_kind": str(getattr(record, "lifecycle_kind", "")),
            "service_ports": list(getattr(record, "service_ports", ())),
            "checkpoint_policy": str(getattr(record, "checkpoint_policy", "")),
            "runtime_profile": dict(getattr(record, "runtime_profile", {})),
            "status": "running",
        }

    async def get_cluster_job(self, job_id):
        return self.jobs.get(job_id)

    async def get_cluster_node(self, node_id):
        item = self.nodes.get(node_id)
        return dict(item) if item is not None else None

    async def upsert_cluster_node(self, payload):
        self.nodes[payload["node_id"]] = dict(payload)

    async def upsert_user_governance_rule(
        self,
        username,
        role,
        max_tasks,
        max_gpu_count,
        max_memory_gb,
        allow_preempt,
        note="",
    ):
        self.rules[username] = {
            "username": username,
            "role": role,
            "max_tasks": max_tasks,
            "max_gpu_count": max_gpu_count,
            "max_memory_gb": max_memory_gb,
            "allow_preempt": allow_preempt,
            "note": note,
        }

    async def get_user_governance_rules(self):
        return dict(self.rules)

    async def get_known_usernames(self):
        return list(self.rules.keys())

    async def delete_user_governance_rule(self, username):
        self.rules.pop(username, None)


class FakePrivacy:
    def resolve_username(self, username, known_usernames):
        del known_usernames
        return username

    def sanitize_governance_rule(self, rule):
        return rule


class FakeClusterControl:
    def __init__(self, store):
        self.store = store
        self.submitted = []

    async def submit_job(self, job_record, *, nodes):
        self.submitted.append((job_record, list(nodes)))
        await self.store.create_cluster_job(job_record)
        return types.SimpleNamespace(plan_type="placement")


class FakeAppState:
    def __init__(self):
        self.agent = FakeAgent()
        self.import_context = FakeImportContext()
        self.scheduler = FakeScheduler()
        self.store = FakeStore()
        self.privacy = FakePrivacy()
        self.cluster_control = FakeClusterControl(self.store)
        self.cluster_nodes = [
            {
                "node_id": "node-a",
                "cluster_id": "cluster-a",
                "label": "Node A",
                "state": "ready",
                "drain_state": "active",
                "schedulable": True,
                "gpu_free": 2,
                "cpu_free": 16,
                "execution_backend": "http_agent",
                "base_url": "http://127.0.0.1:8001",
            }
        ]


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


class GoalRuntimeCapabilityExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_scheduler_and_policy_capabilities_execute_through_shared_registry(self):
        app_state = FakeAppState()
        registry = build_platform_capability_registry(app_state)

        auto_result = await execute_capability(
            registry,
            "scheduler.auto.configure",
            {},
            {"enabled": True},
        )
        carbon_result = await execute_capability(
            registry,
            "scheduler.carbon_budget.configure",
            {},
            {"enabled": True, "daily_budget_kg": 42},
        )
        upsert_result = await execute_capability(
            registry,
            "policy.user_rule.upsert",
            {},
            {
                "username": "alice",
                "role": "protected",
                "max_tasks": 8,
                "max_gpu_count": 2,
                "max_memory_gb": 24,
                "allow_preempt": False,
                "note": "vip",
            },
        )
        delete_result = await execute_capability(
            registry,
            "policy.user_rule.delete",
            {},
            {"username": "alice"},
        )

        self.assertTrue(auto_result["success"])
        self.assertTrue(app_state.scheduler.auto_enabled)
        self.assertTrue(carbon_result["success"])
        self.assertEqual(app_state.scheduler.carbon_budget, (True, 42.0))
        self.assertTrue(upsert_result["success"])
        self.assertEqual(upsert_result["output"]["rule"]["role"], "protected")
        self.assertTrue(delete_result["success"])
        self.assertEqual(app_state.store.rules, {})

    async def test_job_submit_capability_accepts_unified_task_payload(self):
        app_state = FakeAppState()
        registry = build_platform_capability_registry(app_state)

        result = await execute_capability(
            registry,
            "job.submit",
            {},
            {
                "job_id": "job-svc-1",
                "tenant_id": "tenant-a",
                "project_id": "project-a",
                "queue_id": "default",
                "submitter_id": "alice",
                "job_type": "service",
                "task_kind": "inference_service",
                "lifecycle_kind": "service",
                "entrypoint": "python serve.py",
                "args": ["--port", "8080"],
                "env": {"MODEL_ID": "qwen"},
                "resource_request": {"gpu": 1, "cpu": 4},
                "placement_constraints": {"node_group": "service"},
                "priority": 80,
                "preemptible": False,
                "max_retries": 0,
                "timeout_seconds": 0,
                "service_ports": [8080],
                "checkpoint_policy": "none",
                "runtime_profile": {
                    "latency_sensitive": True,
                    "restartable": False,
                    "exclusive_gpu": True,
                    "expected_duration_seconds": 0,
                },
            },
        )

        self.assertTrue(result["success"])
        job = result["output"]["job"]
        self.assertEqual(job["task_kind"], "inference_service")
        self.assertEqual(job["lifecycle_kind"], "service")
        self.assertEqual(job["service_ports"], [8080])
        self.assertEqual(job["checkpoint_policy"], "none")
        self.assertEqual(job["runtime_profile"].get("latency_sensitive"), True)
