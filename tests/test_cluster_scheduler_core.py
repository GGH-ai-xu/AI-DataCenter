import os
import sys
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.cluster_control.control_plane import (  # noqa: E402
    ClusterControlPlaneService,
)
from app.services.cluster_control.execution_orchestrator import (  # noqa: E402
    ExecutionOrchestrator,
)
from app.services.cluster_control.models import JobSpecRecord  # noqa: E402
from app.services.cluster_control.scheduler_core import ClusterSchedulerCore  # noqa: E402


class _FakeStore:
    def __init__(self):
        self.created_jobs = []
        self.jobs = {}
        self.queues = {}
        self.governance_rules = {}
        self.reservation_records = {}
        self.allocation_updates = []
        self.allocation_records = {}
        self.node_records = {}
        self.checkpoint_records = {}

    async def create_cluster_job(self, record):
        self.created_jobs.append(record)
        self.jobs[record.job_id] = {
            "job_id": record.job_id,
            "status": "queued",
            "execution_backend": "",
            "queue_id": record.queue_id,
            "tenant_id": record.tenant_id,
            "project_id": record.project_id,
            "submitter_id": record.submitter_id,
            "job_type": record.job_type,
            "entrypoint": record.entrypoint,
            "args": list(record.args),
            "env": dict(record.env),
            "resource_request": dict(record.resource_request),
            "placement_constraints": dict(record.placement_constraints),
            "priority": record.priority,
            "preemptible": record.preemptible,
            "max_retries": record.max_retries,
            "timeout_seconds": record.timeout_seconds,
            "task_kind": getattr(record, "task_kind", "batch_compute"),
            "lifecycle_kind": getattr(record, "lifecycle_kind", "batch"),
            "service_ports": list(getattr(record, "service_ports", ())),
            "checkpoint_policy": getattr(record, "checkpoint_policy", "none"),
            "runtime_profile": dict(getattr(record, "runtime_profile", {})),
            "last_plan_type": "",
            "last_plan_reason": "",
            "last_error": "",
            "checkpoint_id": "",
            "checkpoint_status": "",
            "checkpoint_manifest_path": "",
            "checkpoint_error": "",
            "checkpoint_updated_at": 0,
        }

    async def get_cluster_job(self, job_id):
        job = self.jobs.get(job_id)
        return dict(job) if job is not None else None

    async def list_cluster_jobs(self):
        return [dict(item) for item in self.jobs.values()]

    async def get_cluster_queue(self, queue_id):
        queue = self.queues.get(queue_id)
        return dict(queue) if queue is not None else None

    async def get_user_governance_rules(self):
        return {key: dict(value) for key, value in self.governance_rules.items()}

    async def update_cluster_job_state(
        self,
        job_id,
        status,
        *,
        execution_backend="",
        plan_type="",
        plan_reason="",
        last_error="",
    ):
        self.jobs[job_id]["status"] = status
        self.jobs[job_id]["execution_backend"] = execution_backend
        self.jobs[job_id]["last_plan_type"] = plan_type
        self.jobs[job_id]["last_plan_reason"] = plan_reason
        self.jobs[job_id]["last_error"] = last_error

    async def update_cluster_allocations_for_job(self, job_id, status):
        self.allocation_updates.append((job_id, status))
        for item in self.allocation_records.values():
            if item["job_id"] == job_id:
                item["status"] = status

    async def upsert_cluster_node(self, payload):
        self.node_records[payload["node_id"]] = dict(payload)

    async def get_cluster_node(self, node_id):
        item = self.node_records.get(node_id)
        return dict(item) if item is not None else None

    async def update_cluster_node_drain_state(self, node_id, drain_state):
        self.node_records[node_id]["drain_state"] = drain_state

    async def create_cluster_allocation(self, payload):
        self.allocation_records[payload["allocation_id"]] = dict(payload)

    async def create_cluster_reservation(self, payload):
        self.reservation_records[payload["reservation_id"]] = dict(payload)

    async def update_cluster_reservation_status(self, reservation_id, status):
        self.reservation_records[reservation_id]["status"] = status

    async def list_cluster_allocations(self):
        return [dict(item) for item in self.allocation_records.values()]

    async def get_cluster_allocation(self, allocation_id):
        item = self.allocation_records.get(allocation_id)
        return dict(item) if item is not None else None

    async def release_cluster_allocation(self, allocation_id):
        self.allocation_records[allocation_id]["status"] = "released"

    async def update_cluster_job_checkpoint(self, job_id, **changes):
        self.jobs[job_id].update(changes)

    async def upsert_cluster_checkpoint(self, payload):
        self.checkpoint_records[str(payload["checkpoint_id"])] = dict(payload)

    async def get_cluster_checkpoint(self, checkpoint_id):
        item = self.checkpoint_records.get(checkpoint_id)
        return dict(item) if item is not None else None

    async def list_cluster_checkpoints(self, *, job_id=""):
        records = [dict(item) for item in self.checkpoint_records.values()]
        if not job_id:
            return records
        return [item for item in records if str(item.get("job_id") or "") == job_id]

    async def get_latest_ready_cluster_checkpoint(self, job_id):
        candidates = [
            dict(item)
            for item in self.checkpoint_records.values()
            if str(item.get("job_id") or "") == job_id
            and str(item.get("status") or "") == "checkpoint_ready"
        ]
        candidates.sort(
            key=lambda item: float(item.get("updated_at") or 0),
            reverse=True,
        )
        return candidates[0] if candidates else None


class _FakeOrchestrator:
    def __init__(
        self,
        store=None,
        *,
        fail_job_id="",
        runtime_jobs_by_node=None,
    ):
        self.calls = []
        self.store = store
        self.fail_job_id = fail_job_id
        self.runtime_jobs_by_node = dict(runtime_jobs_by_node or {})
        self.terminated = []
        self.checkpoint_requests = []
        self.restore_dispatches = []

    async def dispatch_plan(self, job_record, plan, **kwargs):
        self.calls.append((job_record, plan, kwargs))
        if job_record.job_id == self.fail_job_id:
            raise RuntimeError("launch failed")
        if self.store is None:
            return
        await self.store.create_cluster_allocation(
            {
                "allocation_id": f"alloc-{job_record.job_id}",
                "job_id": job_record.job_id,
                "reservation_id": f"res-{job_record.job_id}",
                "node_id": plan.selected_node,
                "gpu_bindings_json": "[\"gpu-0\"]",
                "runtime_job_handle": f"handle-{job_record.job_id}",
                "status": "active",
                "execution_backend": plan.execution_backend or "http_agent",
            }
        )
        await self.store.update_cluster_job_state(
            job_record.job_id,
            "running",
            execution_backend=plan.execution_backend or "http_agent",
        )

    async def list_runtime_jobs(self, node):
        return [
            dict(item)
            for item in self.runtime_jobs_by_node.get(str(node["node_id"]), [])
        ]

    async def terminate_runtime_job(self, node, job_handle):
        self.terminated.append((str(node["node_id"]), job_handle))
        return {
            "job_handle": job_handle,
            "state": "canceled",
            "exit_code": None,
            "last_error": "",
        }

    async def pause_runtime_job(self, node, job_handle):
        return {
            "job_handle": job_handle,
            "state": "paused",
            "last_error": "",
        }

    async def resume_runtime_job(self, node, job_handle):
        return {
            "job_handle": job_handle,
            "state": "running",
            "last_error": "",
        }

    async def checkpoint_runtime_job(self, node, job_handle, payload):
        self.checkpoint_requests.append(
            (
                str(node["node_id"]),
                str(job_handle),
                str(payload["checkpoint_id"]),
            )
        )
        return {
            "job_handle": str(job_handle),
            "checkpoint_id": str(payload["checkpoint_id"]),
            "checkpoint_state": "checkpoint_requested",
            "checkpoint_manifest_path": "",
            "checkpoint_error": "",
        }

    async def restore_plan(self, job_record, plan, checkpoint, *, nodes):
        self.restore_dispatches.append(
            {
                "job_id": job_record.job_id,
                "selected_node": str(plan.selected_node),
                "checkpoint_id": str(checkpoint["checkpoint_id"]),
            }
        )
        if self.store is None:
            return {
                "reservation": {"reservation_id": f"res-{job_record.job_id}"},
                "restore": {"job_handle": f"handle-{job_record.job_id}"},
            }
        await self.store.create_cluster_reservation(
            {
                "reservation_id": f"res-{job_record.job_id}",
                "job_id": job_record.job_id,
                "node_id": str(plan.selected_node),
                "device_ids": tuple(plan.selected_devices),
                "status": "active",
            }
        )
        await self.store.create_cluster_allocation(
            {
                "allocation_id": f"alloc-{job_record.job_id}",
                "job_id": job_record.job_id,
                "reservation_id": f"res-{job_record.job_id}",
                "node_id": str(plan.selected_node),
                "gpu_bindings_json": "[\"gpu-0\"]",
                "runtime_job_handle": f"handle-{job_record.job_id}",
                "status": "active",
                "execution_backend": plan.execution_backend or "http_agent",
            }
        )
        await self.store.update_cluster_job_state(
            job_record.job_id,
            "restoring",
            execution_backend=plan.execution_backend or "http_agent",
        )
        return {
            "reservation": {"reservation_id": f"res-{job_record.job_id}"},
            "restore": {"job_handle": f"handle-{job_record.job_id}"},
        }


class _FakeExecutionBackend:
    def __init__(self):
        self.calls = []

    async def create_reservation(self, node, payload):
        return {
            "reservation_id": payload["reservation_id"],
            "job_id": payload["job_id"],
            "gpu_indexes": list(payload["gpu_indexes"]),
        }

    async def launch_job(self, node, payload):
        return {
            "job_handle": payload["job_handle"],
            "job_id": payload["job_id"],
            "reservation_id": payload["reservation_id"],
            "state": "running",
        }

    async def pause_job(self, node, job_handle):
        self.calls.append(("pause", str(node["node_id"]), job_handle))
        return {"job_handle": job_handle, "state": "paused"}

    async def resume_job(self, node, job_handle):
        self.calls.append(("resume", str(node["node_id"]), job_handle))
        return {"job_handle": job_handle, "state": "running"}

    async def checkpoint_job(self, node, job_handle, payload):
        self.calls.append(
            ("checkpoint", str(node["node_id"]), job_handle, str(payload["checkpoint_id"]))
        )
        return {
            "job_handle": job_handle,
            "checkpoint_id": str(payload["checkpoint_id"]),
            "checkpoint_state": "checkpoint_requested",
        }

    async def restore_job(self, node, payload):
        self.calls.append(
            ("restore", str(node["node_id"]), str(payload["job_handle"]), str(payload["checkpoint_id"]))
        )
        return {
            "job_handle": str(payload["job_handle"]),
            "checkpoint_id": str(payload["checkpoint_id"]),
            "state": "restoring",
        }


def _build_unified_job(**overrides):
    payload = {
        "job_id": "job-unified",
        "tenant_id": "tenant-a",
        "project_id": "project-a",
        "queue_id": "default",
        "submitter_id": "alice",
        "job_type": "batch",
        "task_kind": "batch_compute",
        "lifecycle_kind": "batch",
        "entrypoint": "python train.py",
        "args": (),
        "env": {},
        "resource_request": {"gpu": 1, "cpu": 4},
        "placement_constraints": {},
        "priority": 50,
        "preemptible": True,
        "max_retries": 1,
        "timeout_seconds": 600,
        "service_ports": (),
        "checkpoint_policy": "none",
        "runtime_profile": {
            "expected_duration_seconds": 0,
            "restartable": True,
            "latency_sensitive": False,
            "exclusive_gpu": False,
        },
    }
    payload.update(overrides)
    return JobSpecRecord(**payload)


class ClusterSchedulerCoreTests(unittest.TestCase):
    def test_selects_best_fit_schedulable_node_with_sufficient_capacity(self):
        scheduler = ClusterSchedulerCore()
        job = JobSpecRecord(
            job_id="job-1",
            tenant_id="tenant-a",
            project_id="project-a",
            queue_id="default",
            submitter_id="alice",
            job_type="batch",
            entrypoint="python train.py",
            args=(),
            env={},
            resource_request={"gpu": 1, "cpu": 4},
            placement_constraints={},
            priority=50,
            preemptible=True,
            max_retries=1,
            timeout_seconds=600,
        )

        plan = scheduler.plan_job(
            job,
            nodes=[
                {"node_id": "node-a", "schedulable": True, "gpu_free": 1, "cpu_free": 16},
                {"node_id": "node-b", "schedulable": True, "gpu_free": 4, "cpu_free": 64},
            ],
        )

        self.assertEqual(plan.plan_type, "place")
        self.assertEqual(plan.selected_node, "node-a")
        self.assertEqual(plan.selected_devices, ("gpu-0",))

    def test_returns_queue_wait_plan_when_no_node_matches(self):
        scheduler = ClusterSchedulerCore()
        job = JobSpecRecord(
            job_id="job-2",
            tenant_id="tenant-a",
            project_id="project-a",
            queue_id="default",
            submitter_id="alice",
            job_type="batch",
            entrypoint="python train.py",
            args=(),
            env={},
            resource_request={"gpu": 2},
            placement_constraints={},
            priority=50,
            preemptible=True,
            max_retries=1,
            timeout_seconds=600,
        )

        plan = scheduler.plan_job(
            job,
            nodes=[{"node_id": "node-a", "schedulable": True, "gpu_free": 1}],
        )

        self.assertEqual(plan.plan_type, "wait")
        self.assertEqual(plan.selected_node, "")

    def test_rejects_job_when_queue_is_not_active(self):
        scheduler = ClusterSchedulerCore()
        job = JobSpecRecord(
            job_id="job-rejected",
            tenant_id="tenant-a",
            project_id="project-a",
            queue_id="default",
            submitter_id="alice",
            job_type="batch",
            entrypoint="python train.py",
            args=(),
            env={},
            resource_request={"gpu": 1},
            placement_constraints={},
            priority=50,
            preemptible=True,
            max_retries=1,
            timeout_seconds=600,
        )

        plan = scheduler.plan_job(
            job,
            nodes=[{"node_id": "node-a", "schedulable": True, "gpu_free": 4}],
            queue={"queue_id": "default", "state": "paused", "max_concurrency": 0},
            jobs=[],
        )

        self.assertEqual(plan.plan_type, "reject")
        self.assertIn("queue default is paused", plan.reason)

    def test_returns_queue_wait_when_queue_concurrency_is_reached(self):
        scheduler = ClusterSchedulerCore()
        job = JobSpecRecord(
            job_id="job-wait",
            tenant_id="tenant-a",
            project_id="project-a",
            queue_id="default",
            submitter_id="alice",
            job_type="batch",
            entrypoint="python train.py",
            args=(),
            env={},
            resource_request={"gpu": 1},
            placement_constraints={},
            priority=50,
            preemptible=True,
            max_retries=1,
            timeout_seconds=600,
        )

        plan = scheduler.plan_job(
            job,
            nodes=[{"node_id": "node-a", "schedulable": True, "gpu_free": 4}],
            queue={"queue_id": "default", "state": "active", "max_concurrency": 1},
            jobs=[{"job_id": "job-running", "queue_id": "default", "status": "running"}],
        )

        self.assertEqual(plan.plan_type, "wait")
        self.assertIn("queue default reached max_concurrency 1", plan.reason)

    def test_skips_drained_nodes_when_planning(self):
        scheduler = ClusterSchedulerCore()
        job = JobSpecRecord(
            job_id="job-drain",
            tenant_id="tenant-a",
            project_id="project-a",
            queue_id="default",
            submitter_id="alice",
            job_type="batch",
            entrypoint="python train.py",
            args=(),
            env={},
            resource_request={"gpu": 1},
            placement_constraints={},
            priority=50,
            preemptible=True,
            max_retries=1,
            timeout_seconds=600,
        )

        plan = scheduler.plan_job(
            job,
            nodes=[
                {"node_id": "node-a", "schedulable": True, "drain_state": "drained", "gpu_free": 4},
                {"node_id": "node-b", "schedulable": True, "drain_state": "active", "gpu_free": 1},
            ],
        )

        self.assertEqual(plan.plan_type, "place")
        self.assertEqual(plan.selected_node, "node-b")

    def test_prefers_service_node_without_port_conflict(self):
        scheduler = ClusterSchedulerCore()

        plan = scheduler.plan_job(
            _build_unified_job(
                job_id="job-service",
                job_type="service",
                task_kind="inference_service",
                lifecycle_kind="service",
                service_ports=(8080,),
                preemptible=False,
                runtime_profile={
                    "expected_duration_seconds": 0,
                    "restartable": False,
                    "latency_sensitive": True,
                    "exclusive_gpu": True,
                },
            ),
            nodes=[
                {"node_id": "node-a", "schedulable": True, "drain_state": "active", "gpu_free": 1, "cpu_free": 8},
                {"node_id": "node-b", "schedulable": True, "drain_state": "active", "gpu_free": 2, "cpu_free": 16},
            ],
            allocations=[
                {
                    "allocation_id": "alloc-service",
                    "node_id": "node-a",
                    "status": "active",
                    "lifecycle_kind": "service",
                    "service_ports": [8080],
                }
            ],
        )

        self.assertEqual(plan.selected_node, "node-b")

    def test_skips_nodes_that_do_not_accept_job_lifecycle(self):
        scheduler = ClusterSchedulerCore()

        plan = scheduler.plan_job(
            _build_unified_job(
                job_id="job-session",
                job_type="session",
                task_kind="interactive_session",
                lifecycle_kind="session",
                preemptible=False,
                runtime_profile={
                    "expected_duration_seconds": 0,
                    "restartable": False,
                    "latency_sensitive": False,
                    "exclusive_gpu": True,
                },
            ),
            nodes=[
                {
                    "node_id": "node-a",
                    "schedulable": True,
                    "drain_state": "active",
                    "gpu_free": 1,
                    "cpu_free": 16,
                    "supported_lifecycle_kinds": ("batch",),
                },
                {
                    "node_id": "node-b",
                    "schedulable": True,
                    "drain_state": "active",
                    "gpu_free": 2,
                    "cpu_free": 32,
                    "supported_lifecycle_kinds": ("session", "service"),
                },
            ],
        )

        self.assertEqual(plan.selected_node, "node-b")

    def test_prefers_latency_sensitive_service_for_high_headroom_node(self):
        scheduler = ClusterSchedulerCore()

        plan = scheduler.plan_job(
            _build_unified_job(
                job_id="job-latency",
                job_type="service",
                task_kind="inference_service",
                lifecycle_kind="service",
                preemptible=False,
                runtime_profile={
                    "expected_duration_seconds": 0,
                    "restartable": False,
                    "latency_sensitive": True,
                    "exclusive_gpu": False,
                },
            ),
            nodes=[
                {"node_id": "node-a", "schedulable": True, "drain_state": "active", "gpu_free": 1, "cpu_free": 8},
                {"node_id": "node-b", "schedulable": True, "drain_state": "active", "gpu_free": 4, "cpu_free": 32},
            ],
        )

        self.assertEqual(plan.selected_node, "node-b")

    def test_exclusive_gpu_job_avoids_shared_device_node(self):
        scheduler = ClusterSchedulerCore()

        plan = scheduler.plan_job(
            _build_unified_job(
                job_id="job-exclusive",
                task_kind="training",
                lifecycle_kind="batch",
                runtime_profile={
                    "expected_duration_seconds": 7200,
                    "restartable": True,
                    "latency_sensitive": False,
                    "exclusive_gpu": True,
                },
            ),
            nodes=[
                {
                    "node_id": "node-a",
                    "schedulable": True,
                    "drain_state": "active",
                    "gpu_free": 1,
                    "cpu_free": 16,
                    "device_ids": ("gpu-0",),
                },
                {
                    "node_id": "node-b",
                    "schedulable": True,
                    "drain_state": "active",
                    "gpu_free": 1,
                    "cpu_free": 16,
                    "device_ids": ("gpu-1",),
                },
            ],
            allocations=[
                {
                    "allocation_id": "alloc-running",
                    "node_id": "node-a",
                    "status": "active",
                    "gpu_bindings_json": "[\"gpu-0\"]",
                }
            ],
        )

        self.assertEqual(plan.selected_node, "node-b")

    def test_high_priority_batch_can_preempt_low_priority_batch(self):
        scheduler = ClusterSchedulerCore()

        plan = scheduler.plan_job(
            _build_unified_job(
                job_id="job-target",
                task_kind="training",
                lifecycle_kind="batch",
                priority=90,
                runtime_profile={
                    "expected_duration_seconds": 7200,
                    "restartable": True,
                    "latency_sensitive": False,
                    "exclusive_gpu": True,
                },
            ),
            nodes=[
                {
                    "node_id": "node-a",
                    "schedulable": True,
                    "drain_state": "active",
                    "gpu_free": 0,
                    "cpu_free": 16,
                    "device_ids": ("gpu-0",),
                }
            ],
            jobs=[
                {
                    "job_id": "job-low",
                    "queue_id": "default",
                    "status": "running",
                    "submitter_id": "alice",
                    "priority": 20,
                    "preemptible": True,
                    "task_kind": "batch_compute",
                    "lifecycle_kind": "batch",
                    "runtime_profile": {
                        "restartable": True,
                        "latency_sensitive": False,
                        "exclusive_gpu": False,
                    },
                }
            ],
            allocations=[
                {
                    "allocation_id": "alloc-low",
                    "job_id": "job-low",
                    "node_id": "node-a",
                    "status": "active",
                    "gpu_bindings_json": "[\"gpu-0\"]",
                }
            ],
            governance_rules={"alice": {"allow_preempt": True}},
        )

        self.assertEqual(plan.plan_type, "preempt_then_place")
        self.assertEqual(plan.victim_job_ids, ("job-low",))
        self.assertEqual(plan.required_actions[0]["action"], "cancel_job")

    def test_service_job_is_held_when_only_service_victim_exists(self):
        scheduler = ClusterSchedulerCore()

        plan = scheduler.plan_job(
            _build_unified_job(
                job_id="job-target",
                task_kind="training",
                lifecycle_kind="batch",
                priority=90,
            ),
            nodes=[
                {
                    "node_id": "node-a",
                    "schedulable": True,
                    "drain_state": "active",
                    "gpu_free": 0,
                    "cpu_free": 32,
                    "device_ids": ("gpu-0",),
                }
            ],
            jobs=[
                {
                    "job_id": "job-service",
                    "queue_id": "default",
                    "status": "running",
                    "submitter_id": "svc-user",
                    "priority": 10,
                    "preemptible": False,
                    "task_kind": "inference_service",
                    "lifecycle_kind": "service",
                    "runtime_profile": {
                        "restartable": False,
                        "latency_sensitive": True,
                        "exclusive_gpu": True,
                    },
                }
            ],
            allocations=[
                {
                    "allocation_id": "alloc-service",
                    "job_id": "job-service",
                    "node_id": "node-a",
                    "status": "active",
                    "gpu_bindings_json": "[\"gpu-0\"]",
                    "service_ports": [8080],
                }
            ],
            governance_rules={"svc-user": {"allow_preempt": True}},
        )

        self.assertEqual(plan.plan_type, "hold")
        self.assertIn("victim", plan.reason)


class ClusterControlPlaneServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_submit_job_persists_record_and_dispatches_placement_plan(self):
        store = _FakeStore()
        store.queues["default"] = {
            "queue_id": "default",
            "name": "Default",
            "state": "active",
            "default_priority": 50,
            "max_concurrency": 0,
        }
        orchestrator = _FakeOrchestrator(store)
        scheduler = ClusterSchedulerCore()
        service = ClusterControlPlaneService(store, scheduler, orchestrator)
        job = JobSpecRecord(
            job_id="job-3",
            tenant_id="tenant-a",
            project_id="project-a",
            queue_id="default",
            submitter_id="alice",
            job_type="batch",
            entrypoint="python train.py",
            args=(),
            env={},
            resource_request={"gpu": 1},
            placement_constraints={},
            priority=50,
            preemptible=True,
            max_retries=1,
            timeout_seconds=600,
        )

        plan = await service.submit_job(
            job,
            nodes=[{"node_id": "node-a", "schedulable": True, "gpu_free": 1}],
        )

        self.assertEqual(store.created_jobs[0].job_id, "job-3")
        self.assertEqual(plan.plan_type, "place")
        self.assertEqual(orchestrator.calls[0][1].selected_node, "node-a")

    async def test_submit_job_marks_job_pending_when_queue_waits(self):
        store = _FakeStore()
        store.queues["default"] = {
            "queue_id": "default",
            "name": "Default",
            "state": "active",
            "default_priority": 50,
            "max_concurrency": 1,
        }
        store.jobs["job-running"] = {
            "job_id": "job-running",
            "queue_id": "default",
            "tenant_id": "tenant-a",
            "project_id": "project-a",
            "submitter_id": "alice",
            "job_type": "batch",
            "entrypoint": "python train.py",
            "args": [],
            "env": {},
            "resource_request": {"gpu": 1},
            "placement_constraints": {},
            "priority": 50,
            "preemptible": True,
            "max_retries": 1,
            "timeout_seconds": 600,
            "status": "running",
            "execution_backend": "http_agent",
            "last_plan_type": "",
            "last_plan_reason": "",
        }
        orchestrator = _FakeOrchestrator(store)
        service = ClusterControlPlaneService(store, ClusterSchedulerCore(), orchestrator)
        job = JobSpecRecord(
            job_id="job-pending",
            tenant_id="tenant-a",
            project_id="project-a",
            queue_id="default",
            submitter_id="alice",
            job_type="batch",
            entrypoint="python train.py",
            args=(),
            env={},
            resource_request={"gpu": 1},
            placement_constraints={},
            priority=50,
            preemptible=True,
            max_retries=1,
            timeout_seconds=600,
        )

        plan = await service.submit_job(
            job,
            nodes=[{"node_id": "node-a", "schedulable": True, "gpu_free": 4}],
        )

        self.assertEqual(plan.plan_type, "wait")
        self.assertEqual(store.jobs["job-pending"]["status"], "pending")
        self.assertEqual(store.jobs["job-pending"]["last_plan_type"], "wait")
        self.assertIn("max_concurrency", store.jobs["job-pending"]["last_plan_reason"])
        self.assertEqual(orchestrator.calls, [])

    async def test_submit_job_marks_job_rejected_when_queue_is_inactive(self):
        store = _FakeStore()
        store.queues["default"] = {
            "queue_id": "default",
            "name": "Default",
            "state": "paused",
            "default_priority": 50,
            "max_concurrency": 0,
        }
        orchestrator = _FakeOrchestrator(store)
        service = ClusterControlPlaneService(store, ClusterSchedulerCore(), orchestrator)
        job = JobSpecRecord(
            job_id="job-rejected",
            tenant_id="tenant-a",
            project_id="project-a",
            queue_id="default",
            submitter_id="alice",
            job_type="batch",
            entrypoint="python train.py",
            args=(),
            env={},
            resource_request={"gpu": 1},
            placement_constraints={},
            priority=50,
            preemptible=True,
            max_retries=1,
            timeout_seconds=600,
        )

        plan = await service.submit_job(
            job,
            nodes=[{"node_id": "node-a", "schedulable": True, "gpu_free": 4}],
        )

        self.assertEqual(plan.plan_type, "reject")
        self.assertEqual(store.jobs["job-rejected"]["status"], "rejected")
        self.assertEqual(store.jobs["job-rejected"]["last_plan_type"], "reject")
        self.assertIn("queue default is paused", store.jobs["job-rejected"]["last_plan_reason"])
        self.assertEqual(orchestrator.calls, [])

    async def test_submit_job_marks_job_failed_when_dispatch_raises(self):
        store = _FakeStore()
        store.queues["default"] = {
            "queue_id": "default",
            "name": "Default",
            "state": "active",
            "default_priority": 50,
            "max_concurrency": 0,
        }
        service = ClusterControlPlaneService(
            store,
            ClusterSchedulerCore(),
            _FakeOrchestrator(store, fail_job_id="job-failed"),
        )
        job = JobSpecRecord(
            job_id="job-failed",
            tenant_id="tenant-a",
            project_id="project-a",
            queue_id="default",
            submitter_id="alice",
            job_type="batch",
            entrypoint="python train.py",
            args=(),
            env={},
            resource_request={"gpu": 1},
            placement_constraints={},
            priority=50,
            preemptible=True,
            max_retries=1,
            timeout_seconds=600,
        )

        with self.assertRaisesRegex(RuntimeError, "launch failed"):
            await service.submit_job(
                job,
                nodes=[{"node_id": "node-a", "schedulable": True, "gpu_free": 4}],
            )

        self.assertEqual(store.jobs["job-failed"]["status"], "failed")
        self.assertEqual(store.jobs["job-failed"]["last_error"], "launch failed")

    async def test_reconcile_and_dispatch_moves_pending_job_to_running(self):
        store = _FakeStore()
        store.queues["default"] = {
            "queue_id": "default",
            "name": "Default",
            "state": "active",
            "default_priority": 50,
            "max_concurrency": 0,
        }
        job = JobSpecRecord(
            job_id="job-reconcile",
            tenant_id="tenant-a",
            project_id="project-a",
            queue_id="default",
            submitter_id="alice",
            job_type="batch",
            entrypoint="python train.py",
            args=(),
            env={},
            resource_request={"gpu": 1},
            placement_constraints={},
            priority=50,
            preemptible=True,
            max_retries=1,
            timeout_seconds=600,
        )
        await store.create_cluster_job(job)
        await store.update_cluster_job_state("job-reconcile", "pending")
        service = ClusterControlPlaneService(
            store,
            ClusterSchedulerCore(),
            _FakeOrchestrator(store),
        )

        summary = await service.reconcile_and_dispatch(
            nodes=[{"node_id": "node-a", "schedulable": True, "gpu_free": 4}],
        )

        self.assertEqual(summary["dispatched"], 1)
        self.assertEqual(store.jobs["job-reconcile"]["status"], "running")
        self.assertIn("alloc-job-reconcile", store.allocation_records)

    async def test_reconcile_and_dispatch_releases_terminal_runtime_and_dispatches_next_job(self):
        store = _FakeStore()
        store.queues["default"] = {
            "queue_id": "default",
            "name": "Default",
            "state": "active",
            "default_priority": 50,
            "max_concurrency": 0,
        }
        await store.upsert_cluster_node(
            {
                "node_id": "node-a",
                "cluster_id": "cluster-a",
                "label": "Node A",
                "state": "ready",
                "drain_state": "active",
                "execution_backend": "http_agent",
                "metadata": {},
            }
        )
        running_job = JobSpecRecord(
            job_id="job-running",
            tenant_id="tenant-a",
            project_id="project-a",
            queue_id="default",
            submitter_id="alice",
            job_type="batch",
            entrypoint="python train.py",
            args=(),
            env={},
            resource_request={"gpu": 1},
            placement_constraints={},
            priority=60,
            preemptible=True,
            max_retries=1,
            timeout_seconds=600,
        )
        pending_job = JobSpecRecord(
            job_id="job-next",
            tenant_id="tenant-a",
            project_id="project-a",
            queue_id="default",
            submitter_id="alice",
            job_type="batch",
            entrypoint="python train.py",
            args=(),
            env={},
            resource_request={"gpu": 1},
            placement_constraints={},
            priority=50,
            preemptible=True,
            max_retries=1,
            timeout_seconds=600,
        )
        await store.create_cluster_job(running_job)
        await store.update_cluster_job_state("job-running", "running", execution_backend="http_agent")
        await store.create_cluster_reservation(
            {
                "reservation_id": "res-job-running",
                "job_id": "job-running",
                "node_id": "node-a",
                "device_ids": ("gpu-0",),
                "status": "active",
            }
        )
        await store.create_cluster_allocation(
            {
                "allocation_id": "alloc-job-running",
                "job_id": "job-running",
                "reservation_id": "res-job-running",
                "node_id": "node-a",
                "gpu_bindings_json": "[\"gpu-0\"]",
                "runtime_job_handle": "handle-job-running",
                "status": "active",
                "execution_backend": "http_agent",
            }
        )
        await store.create_cluster_job(pending_job)
        await store.update_cluster_job_state("job-next", "pending")
        service = ClusterControlPlaneService(
            store,
            ClusterSchedulerCore(),
            _FakeOrchestrator(
                store,
                runtime_jobs_by_node={
                    "node-a": [
                        {
                            "job_handle": "handle-job-running",
                            "job_id": "job-running",
                            "state": "succeeded",
                            "exit_code": 0,
                            "last_error": "",
                        }
                    ]
                },
            ),
        )

        summary = await service.reconcile_and_dispatch(
            nodes=[
                {
                    "node_id": "node-a",
                    "schedulable": True,
                    "gpu_free": 4,
                    "execution_backend": "http_agent",
                }
            ],
        )

        self.assertEqual(store.jobs["job-running"]["status"], "succeeded")
        self.assertEqual(store.allocation_records["alloc-job-running"]["status"], "released")
        self.assertEqual(store.reservation_records["res-job-running"]["status"], "released")
        self.assertEqual(store.jobs["job-next"]["status"], "running")
        self.assertEqual(summary["dispatched"], 1)

    async def test_reconcile_and_dispatch_marks_victim_checkpointing_before_followup_dispatch(self):
        store = _FakeStore()
        store.queues["default"] = {
            "queue_id": "default",
            "name": "Default",
            "state": "active",
            "default_priority": 50,
            "max_concurrency": 0,
        }
        store.governance_rules["alice"] = {"allow_preempt": True}
        await store.create_cluster_job(
            _build_unified_job(
                job_id="job-low",
                task_kind="batch_compute",
                lifecycle_kind="batch",
                priority=10,
                checkpoint_policy="app_managed",
            )
        )
        await store.create_cluster_job(
            _build_unified_job(
                job_id="job-target",
                task_kind="training",
                lifecycle_kind="batch",
                priority=90,
            )
        )
        await store.update_cluster_job_state(
            "job-low",
            "running",
            execution_backend="http_agent",
        )
        await store.update_cluster_job_state("job-target", "pending")
        await store.upsert_cluster_node(
            {
                "node_id": "node-a",
                "cluster_id": "cluster-a",
                "label": "Node A",
                "state": "ready",
                "drain_state": "active",
                "execution_backend": "http_agent",
                "metadata": {},
            }
        )
        await store.create_cluster_allocation(
            {
                "allocation_id": "alloc-low",
                "job_id": "job-low",
                "reservation_id": "res-low",
                "node_id": "node-a",
                "gpu_bindings_json": "[\"gpu-0\"]",
                "runtime_job_handle": "handle-job-low",
                "status": "active",
                "execution_backend": "http_agent",
            }
        )
        service = ClusterControlPlaneService(
            store,
            ClusterSchedulerCore(),
            _FakeOrchestrator(store),
        )

        summary = await service.reconcile_and_dispatch(
            nodes=[
                {
                    "node_id": "node-a",
                    "schedulable": True,
                    "drain_state": "active",
                    "gpu_free": 0,
                    "cpu_free": 16,
                    "device_ids": ("gpu-0",),
                    "execution_backend": "http_agent",
                }
            ],
        )

        self.assertEqual(store.jobs["job-low"]["status"], "preempting")
        self.assertEqual(store.jobs["job-target"]["status"], "pending")
        self.assertEqual(summary["jobs"][0]["job_id"], "job-low")
        self.assertEqual(summary["jobs"][0]["status"], "checkpointing")

    async def test_reconcile_and_dispatch_requests_checkpoint_for_app_managed_victim(self):
        store = _FakeStore()
        store.queues["default"] = {
            "queue_id": "default",
            "name": "Default",
            "state": "active",
            "default_priority": 50,
            "max_concurrency": 0,
        }
        store.governance_rules["alice"] = {"allow_preempt": True}
        await store.upsert_cluster_node(
            {
                "node_id": "node-a",
                "cluster_id": "cluster-a",
                "label": "Node A",
                "state": "ready",
                "drain_state": "active",
                "execution_backend": "http_agent",
                "metadata": {},
            }
        )
        await store.create_cluster_job(
            _build_unified_job(
                job_id="job-low",
                priority=10,
                checkpoint_policy="app_managed",
            )
        )
        await store.create_cluster_job(
            _build_unified_job(
                job_id="job-target",
                task_kind="training",
                priority=90,
            )
        )
        await store.update_cluster_job_state("job-low", "running", execution_backend="http_agent")
        await store.update_cluster_job_state("job-target", "pending")
        await store.create_cluster_reservation(
            {
                "reservation_id": "res-low",
                "job_id": "job-low",
                "node_id": "node-a",
                "device_ids": ("gpu-0",),
                "status": "active",
            }
        )
        await store.create_cluster_allocation(
            {
                "allocation_id": "alloc-low",
                "job_id": "job-low",
                "reservation_id": "res-low",
                "node_id": "node-a",
                "gpu_bindings_json": "[\"gpu-0\"]",
                "runtime_job_handle": "handle-job-low",
                "status": "active",
                "execution_backend": "http_agent",
            }
        )
        orchestrator = _FakeOrchestrator(store)
        service = ClusterControlPlaneService(store, ClusterSchedulerCore(), orchestrator)

        await service.reconcile_and_dispatch(
            nodes=[
                {
                    "node_id": "node-a",
                    "schedulable": True,
                    "drain_state": "active",
                    "gpu_free": 0,
                    "cpu_free": 16,
                    "device_ids": ("gpu-0",),
                    "execution_backend": "http_agent",
                }
            ],
        )

        self.assertEqual(
            orchestrator.checkpoint_requests,
            [("node-a", "handle-job-low", store.jobs["job-low"]["checkpoint_id"])],
        )
        self.assertEqual(store.jobs["job-low"]["checkpoint_status"], "checkpoint_requested")
        self.assertEqual(store.allocation_updates, [("job-low", "checkpointing")])

    async def test_reconcile_and_dispatch_hard_reclaims_non_checkpoint_victim(self):
        store = _FakeStore()
        store.queues["default"] = {
            "queue_id": "default",
            "name": "Default",
            "state": "active",
            "default_priority": 50,
            "max_concurrency": 0,
        }
        await store.upsert_cluster_node(
            {
                "node_id": "node-a",
                "cluster_id": "cluster-a",
                "label": "Node A",
                "state": "ready",
                "drain_state": "active",
                "execution_backend": "http_agent",
                "metadata": {},
            }
        )
        await store.create_cluster_job(_build_unified_job(job_id="job-low", priority=10))
        await store.create_cluster_job(
            _build_unified_job(job_id="job-target", task_kind="training", priority=90)
        )
        await store.update_cluster_job_state("job-low", "running", execution_backend="http_agent")
        await store.update_cluster_job_state("job-target", "pending")
        await store.create_cluster_reservation(
            {
                "reservation_id": "res-low",
                "job_id": "job-low",
                "node_id": "node-a",
                "device_ids": ("gpu-0",),
                "status": "active",
            }
        )
        await store.create_cluster_allocation(
            {
                "allocation_id": "alloc-low",
                "job_id": "job-low",
                "reservation_id": "res-low",
                "node_id": "node-a",
                "gpu_bindings_json": "[\"gpu-0\"]",
                "runtime_job_handle": "handle-job-low",
                "status": "active",
                "execution_backend": "http_agent",
            }
        )
        orchestrator = _FakeOrchestrator(store)
        service = ClusterControlPlaneService(store, ClusterSchedulerCore(), orchestrator)

        summary = await service.reconcile_and_dispatch(
            nodes=[
                {
                    "node_id": "node-a",
                    "schedulable": True,
                    "drain_state": "active",
                    "gpu_free": 0,
                    "cpu_free": 16,
                    "device_ids": ("gpu-0",),
                    "execution_backend": "http_agent",
                }
            ],
        )

        self.assertEqual(orchestrator.terminated, [("node-a", "handle-job-low")])
        self.assertEqual(orchestrator.checkpoint_requests, [])
        self.assertEqual(store.jobs["job-low"]["status"], "preempted")
        self.assertEqual(store.allocation_records["alloc-low"]["status"], "released")
        self.assertEqual(store.reservation_records["res-low"]["status"], "released")
        self.assertEqual(store.jobs["job-target"]["status"], "pending")
        self.assertEqual(summary["jobs"][0]["status"], "preempted")

    async def test_manual_preempt_hard_reclaims_non_checkpoint_job(self):
        store = _FakeStore()
        await store.upsert_cluster_node(
            {
                "node_id": "node-a",
                "cluster_id": "cluster-a",
                "label": "Node A",
                "state": "ready",
                "drain_state": "active",
                "execution_backend": "http_agent",
                "metadata": {},
            }
        )
        await store.create_cluster_job(_build_unified_job(job_id="job-low"))
        await store.update_cluster_job_state("job-low", "running", execution_backend="http_agent")
        await store.create_cluster_reservation(
            {
                "reservation_id": "res-low",
                "job_id": "job-low",
                "node_id": "node-a",
                "device_ids": ("gpu-0",),
                "status": "active",
            }
        )
        await store.create_cluster_allocation(
            {
                "allocation_id": "alloc-low",
                "job_id": "job-low",
                "reservation_id": "res-low",
                "node_id": "node-a",
                "gpu_bindings_json": "[\"gpu-0\"]",
                "runtime_job_handle": "handle-job-low",
                "status": "active",
                "execution_backend": "http_agent",
            }
        )
        orchestrator = _FakeOrchestrator(store)
        service = ClusterControlPlaneService(store, ClusterSchedulerCore(), orchestrator)

        updated = await service.preempt_job("job-low")

        self.assertEqual(orchestrator.terminated, [("node-a", "handle-job-low")])
        self.assertEqual(orchestrator.checkpoint_requests, [])
        self.assertEqual(updated["status"], "preempted")
        self.assertEqual(store.allocation_records["alloc-low"]["status"], "released")
        self.assertEqual(store.reservation_records["res-low"]["status"], "released")

    async def test_reconcile_and_dispatch_releases_checkpoint_ready_victim_and_advances_target(self):
        store = _FakeStore()
        store.queues["default"] = {
            "queue_id": "default",
            "name": "Default",
            "state": "active",
            "default_priority": 50,
            "max_concurrency": 0,
        }
        await store.upsert_cluster_node(
            {
                "node_id": "node-a",
                "cluster_id": "cluster-a",
                "label": "Node A",
                "state": "ready",
                "drain_state": "active",
                "execution_backend": "http_agent",
                "metadata": {},
            }
        )
        await store.create_cluster_job(
            _build_unified_job(
                job_id="job-low",
                priority=10,
                checkpoint_policy="app_managed",
            )
        )
        await store.create_cluster_job(
            _build_unified_job(
                job_id="job-target",
                task_kind="training",
                priority=90,
            )
        )
        await store.update_cluster_job_state("job-low", "preempting", execution_backend="http_agent")
        await store.update_cluster_job_checkpoint(
            "job-low",
            checkpoint_id="ckpt-low",
            checkpoint_status="checkpoint_requested",
        )
        await store.create_cluster_reservation(
            {
                "reservation_id": "res-low",
                "job_id": "job-low",
                "node_id": "node-a",
                "device_ids": ("gpu-0",),
                "status": "active",
            }
        )
        await store.create_cluster_allocation(
            {
                "allocation_id": "alloc-low",
                "job_id": "job-low",
                "reservation_id": "res-low",
                "node_id": "node-a",
                "gpu_bindings_json": "[\"gpu-0\"]",
                "runtime_job_handle": "handle-job-low",
                "status": "checkpointing",
                "execution_backend": "http_agent",
            }
        )
        store.jobs["job-target"]["status"] = "pending"
        orchestrator = _FakeOrchestrator(
            store,
            runtime_jobs_by_node={
                "node-a": [
                    {
                        "job_handle": "handle-job-low",
                        "job_id": "job-low",
                        "state": "running",
                        "checkpoint_id": "ckpt-low",
                        "checkpoint_state": "checkpoint_ready",
                        "checkpoint_manifest_path": "/tmp/ckpt-low.json",
                        "checkpoint_error": "",
                        "finished_at": 12.0,
                    }
                ]
            },
        )
        service = ClusterControlPlaneService(store, ClusterSchedulerCore(), orchestrator)

        summary = await service.reconcile_and_dispatch(
            nodes=[
                {
                    "node_id": "node-a",
                    "schedulable": True,
                    "drain_state": "active",
                    "gpu_free": 1,
                    "cpu_free": 16,
                    "device_ids": ("gpu-0",),
                    "execution_backend": "http_agent",
                }
            ],
        )

        self.assertEqual(store.jobs["job-low"]["status"], "preempted")
        self.assertEqual(store.allocation_records["alloc-low"]["status"], "released")
        self.assertEqual(store.reservation_records["res-low"]["status"], "released")
        self.assertEqual(store.jobs["job-target"]["status"], "running")
        self.assertEqual(orchestrator.terminated, [("node-a", "handle-job-low")])
        self.assertEqual(summary["dispatched"], 1)

    async def test_reconcile_and_dispatch_restores_preempted_job_from_ready_checkpoint(self):
        store = _FakeStore()
        store.queues["default"] = {
            "queue_id": "default",
            "name": "Default",
            "state": "active",
            "default_priority": 50,
            "max_concurrency": 0,
        }
        await store.create_cluster_job(
            _build_unified_job(
                job_id="job-restore",
                priority=20,
                checkpoint_policy="app_managed",
            )
        )
        await store.update_cluster_job_state("job-restore", "preempted")
        await store.update_cluster_job_checkpoint(
            "job-restore",
            checkpoint_id="ckpt-restore",
            checkpoint_status="checkpoint_ready",
            checkpoint_manifest_path="/tmp/ckpt-restore.json",
            checkpoint_updated_at=20.0,
        )
        await store.upsert_cluster_checkpoint(
            {
                "checkpoint_id": "ckpt-restore",
                "job_id": "job-restore",
                "allocation_id": "alloc-old",
                "node_id": "node-a",
                "runtime_job_handle": "handle-old",
                "status": "checkpoint_ready",
                "manifest_path": "/tmp/ckpt-restore.json",
                "error": "",
                "created_at": 20.0,
                "updated_at": 20.0,
            }
        )
        orchestrator = _FakeOrchestrator(store)
        service = ClusterControlPlaneService(store, ClusterSchedulerCore(), orchestrator)

        summary = await service.reconcile_and_dispatch(
            nodes=[
                {
                    "node_id": "node-a",
                    "schedulable": True,
                    "drain_state": "active",
                    "gpu_free": 1,
                    "cpu_free": 16,
                    "device_ids": ("gpu-0",),
                    "execution_backend": "http_agent",
                }
            ],
        )

        self.assertEqual(store.jobs["job-restore"]["status"], "restoring")
        self.assertEqual(
            orchestrator.restore_dispatches,
            [{"job_id": "job-restore", "selected_node": "node-a", "checkpoint_id": "ckpt-restore"}],
        )
        self.assertEqual(summary["dispatched"], 1)

    async def test_cancel_running_job_terminates_runtime_and_releases_resources(self):
        store = _FakeStore()
        await store.upsert_cluster_node(
            {
                "node_id": "node-a",
                "cluster_id": "cluster-a",
                "label": "Node A",
                "state": "ready",
                "drain_state": "active",
                "execution_backend": "http_agent",
                "metadata": {},
            }
        )
        job = JobSpecRecord(
            job_id="job-cancel-runtime",
            tenant_id="tenant-a",
            project_id="project-a",
            queue_id="default",
            submitter_id="alice",
            job_type="batch",
            entrypoint="python train.py",
            args=(),
            env={},
            resource_request={"gpu": 1},
            placement_constraints={},
            priority=50,
            preemptible=True,
            max_retries=1,
            timeout_seconds=600,
        )
        await store.create_cluster_job(job)
        await store.update_cluster_job_state(
            "job-cancel-runtime",
            "running",
            execution_backend="http_agent",
        )
        await store.create_cluster_reservation(
            {
                "reservation_id": "res-job-cancel-runtime",
                "job_id": "job-cancel-runtime",
                "node_id": "node-a",
                "device_ids": ("gpu-0",),
                "status": "active",
            }
        )
        await store.create_cluster_allocation(
            {
                "allocation_id": "alloc-job-cancel-runtime",
                "job_id": "job-cancel-runtime",
                "reservation_id": "res-job-cancel-runtime",
                "node_id": "node-a",
                "gpu_bindings_json": "[\"gpu-0\"]",
                "runtime_job_handle": "handle-job-cancel-runtime",
                "status": "active",
                "execution_backend": "http_agent",
            }
        )
        orchestrator = _FakeOrchestrator(store)
        service = ClusterControlPlaneService(
            store,
            ClusterSchedulerCore(),
            orchestrator,
        )

        canceled = await service.cancel_job("job-cancel-runtime")

        self.assertEqual(canceled["status"], "canceled")
        self.assertEqual(orchestrator.terminated, [("node-a", "handle-job-cancel-runtime")])
        self.assertEqual(
            store.allocation_records["alloc-job-cancel-runtime"]["status"],
            "released",
        )
        self.assertEqual(
            store.reservation_records["res-job-cancel-runtime"]["status"],
            "released",
        )

    async def test_list_jobs_projects_runtime_job_handle_from_allocations(self):
        store = _FakeStore()
        service = ClusterControlPlaneService(
            store,
            ClusterSchedulerCore(),
            _FakeOrchestrator(),
        )
        job = JobSpecRecord(
            job_id="job-runtime",
            tenant_id="tenant-a",
            project_id="project-a",
            queue_id="default",
            submitter_id="alice",
            job_type="batch",
            entrypoint="python train.py",
            args=(),
            env={},
            resource_request={"gpu": 1},
            placement_constraints={},
            priority=50,
            preemptible=True,
            max_retries=1,
            timeout_seconds=600,
        )
        await store.create_cluster_job(job)
        await store.create_cluster_allocation(
            {
                "allocation_id": "alloc-job-runtime",
                "job_id": "job-runtime",
                "reservation_id": "res-job-runtime",
                "node_id": "node-a",
                "gpu_bindings_json": "[\"gpu-0\"]",
                "runtime_job_handle": "handle-job-runtime",
                "status": "active",
                "execution_backend": "http_agent",
            }
        )

        listed = await service.list_jobs()
        loaded = await service.get_job("job-runtime")

        self.assertEqual(listed[0]["runtime_job_handle"], "handle-job-runtime")
        self.assertEqual(loaded["runtime_job_handle"], "handle-job-runtime")

    async def test_job_lifecycle_updates_job_and_allocation_states(self):
        store = _FakeStore()
        service = ClusterControlPlaneService(
            store,
            ClusterSchedulerCore(),
            _FakeOrchestrator(),
        )
        job = JobSpecRecord(
            job_id="job-4",
            tenant_id="tenant-a",
            project_id="project-a",
            queue_id="default",
            submitter_id="alice",
            job_type="batch",
            entrypoint="python train.py",
            args=(),
            env={},
            resource_request={"gpu": 1},
            placement_constraints={},
            priority=50,
            preemptible=True,
            max_retries=1,
            timeout_seconds=600,
        )
        await store.create_cluster_job(job)
        await store.update_cluster_job_state("job-4", "running", execution_backend="http_agent")
        await store.upsert_cluster_node(
            {
                "node_id": "node-a",
                "cluster_id": "cluster-a",
                "label": "Node A",
                "state": "ready",
                "drain_state": "active",
                "execution_backend": "http_agent",
                "metadata": {},
            }
        )
        await store.create_cluster_allocation(
            {
                "allocation_id": "alloc-job-4",
                "job_id": "job-4",
                "reservation_id": "res-job-4",
                "node_id": "node-a",
                "gpu_bindings_json": "[\"gpu-0\"]",
                "runtime_job_handle": "handle-job-4",
                "status": "active",
                "execution_backend": "http_agent",
            }
        )
        await store.create_cluster_reservation(
            {
                "reservation_id": "res-job-4",
                "job_id": "job-4",
                "node_id": "node-a",
                "device_ids": ("gpu-0",),
                "status": "active",
            }
        )

        paused = await service.pause_job("job-4")
        resumed = await service.resume_job("job-4")
        canceled = await service.cancel_job("job-4")

        self.assertEqual(paused["status"], "paused")
        self.assertEqual(resumed["status"], "running")
        self.assertEqual(canceled["status"], "canceled")
        self.assertEqual(
            store.allocation_updates,
            [("job-4", "paused"), ("job-4", "active")],
        )
        self.assertEqual(store.allocation_records["alloc-job-4"]["status"], "released")

    async def test_node_drain_and_allocation_release_update_store_state(self):
        store = _FakeStore()
        service = ClusterControlPlaneService(
            store,
            ClusterSchedulerCore(),
            _FakeOrchestrator(),
        )
        await store.upsert_cluster_node(
            {
                "node_id": "node-a",
                "cluster_id": "cluster-a",
                "label": "Node A",
                "state": "ready",
                "drain_state": "active",
                "execution_backend": "http_agent",
                "metadata": {},
            }
        )
        await store.create_cluster_allocation(
            {
                "allocation_id": "alloc-1",
                "job_id": "job-1",
                "node_id": "node-a",
                "gpu_bindings_json": "[\"gpu-0\"]",
                "status": "active",
                "execution_backend": "http_agent",
            }
        )

        drained = await service.drain_node("node-a")
        released = await service.release_allocation("alloc-1")
        undrained = await service.undrain_node("node-a")

        self.assertEqual(drained["drain_state"], "drained")
        self.assertEqual(released["status"], "released")
        self.assertEqual(undrained["drain_state"], "active")


class ExecutionOrchestratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_dispatch_plan_persists_reservation_and_runtime_handle(self):
        store = _FakeStore()
        orchestrator = ExecutionOrchestrator(
            store,
            {"http_agent": _FakeExecutionBackend()},
        )
        job = JobSpecRecord(
            job_id="job-orch",
            tenant_id="tenant-a",
            project_id="project-a",
            queue_id="default",
            submitter_id="alice",
            job_type="batch",
            entrypoint="python train.py",
            args=(),
            env={},
            resource_request={"gpu": 1},
            placement_constraints={},
            priority=50,
            preemptible=True,
            max_retries=1,
            timeout_seconds=600,
        )

        plan = type(
            "Plan",
            (),
            {
                "selected_node": "node-a",
                "selected_devices": ("gpu-0",),
                "execution_backend": "http_agent",
            },
        )()
        await store.create_cluster_job(job)

        await orchestrator.dispatch_plan(
            job,
            plan=plan,
            nodes=[
                {
                    "node_id": "node-a",
                    "execution_backend": "http_agent",
                    "base_url": "http://127.0.0.1:8001",
                }
            ],
        )

        self.assertIn("res-job-orch", store.reservation_records)
        self.assertEqual(
            store.allocation_records["alloc-job-orch"]["runtime_job_handle"],
            "handle-job-orch",
        )

    async def test_forwards_pause_resume_checkpoint_and_restore(self):
        store = _FakeStore()
        backend = _FakeExecutionBackend()
        orchestrator = ExecutionOrchestrator(store, {"http_agent": backend})
        node = {
            "node_id": "node-a",
            "execution_backend": "http_agent",
            "base_url": "http://127.0.0.1:8001",
        }

        await orchestrator.pause_runtime_job(node, "handle-1")
        await orchestrator.resume_runtime_job(node, "handle-1")
        await orchestrator.checkpoint_runtime_job(
            node,
            "handle-1",
            {"checkpoint_id": "ckpt-1", "timeout_seconds": 15},
        )
        await orchestrator.restore_runtime_job(
            node,
            {
                "job_handle": "handle-2",
                "checkpoint_id": "ckpt-1",
                "reservation_id": "res-2",
                "job_id": "job-2",
                "command": ["python", "-c", "print('ok')"],
                "env": {},
            },
        )

        self.assertEqual(
            backend.calls,
            [
                ("pause", "node-a", "handle-1"),
                ("resume", "node-a", "handle-1"),
                ("checkpoint", "node-a", "handle-1", "ckpt-1"),
                ("restore", "node-a", "handle-2", "ckpt-1"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
