import os
import sys
import types
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.goal_runtime.goal_spec import GoalSpec  # noqa: E402
from app.services.goal_runtime.permission_policy import requires_approval  # noqa: E402
from app.services.goal_runtime.platform_capabilities import (  # noqa: E402
    build_platform_capability_registry,
)
from app.services.goal_runtime.planner import build_initial_plan  # noqa: E402


def _build_state():
    return types.SimpleNamespace(
        cluster_control=object(),
        agent=object(),
        scheduler=object(),
        import_context=object(),
        store=object(),
    )


class GoalRuntimeClusterCapabilityTests(unittest.TestCase):
    def test_cluster_job_capabilities_are_registered(self):
        registry = build_platform_capability_registry(_build_state())

        self.assertEqual(registry.get("job.submit").definition.domain, "jobs")
        self.assertEqual(registry.get("job.plan").definition.domain, "jobs")
        self.assertEqual(registry.get("job.requeue").definition.domain, "jobs")
        self.assertEqual(registry.get("job.preempt").definition.domain, "jobs")
        self.assertEqual(registry.get("job.checkpoint").definition.domain, "jobs")
        self.assertEqual(registry.get("job.restore").definition.domain, "jobs")
        self.assertEqual(registry.get("job.plan").definition.side_effect_level, "observe")
        self.assertEqual(registry.get("reschedule.plan").definition.domain, "scheduler")
        self.assertEqual(registry.get("queue.reconcile").definition.domain, "queues")
        self.assertEqual(
            registry.get("queue.status.read").definition.side_effect_level,
            "observe",
        )
        self.assertEqual(registry.get("node.drain").definition.domain, "nodes")
        self.assertEqual(registry.get("allocation.release").definition.domain, "allocations")

    def test_low_permission_job_submit_requires_approval(self):
        registry = build_platform_capability_registry(_build_state())

        self.assertTrue(requires_approval(registry.get("job.submit").definition, "low"))
        self.assertFalse(requires_approval(registry.get("job.plan").definition, "low"))
        self.assertTrue(requires_approval(registry.get("queue.reconcile").definition, "low"))

    def test_planner_maps_submit_job_action_to_job_submit_capability(self):
        registry = build_platform_capability_registry(_build_state())
        goal_spec = GoalSpec(
            session_id="sess-job",
            raw_message="提交训练作业",
            goal_type="runtime_control",
            permission_mode="low",
            scope_gpu_indexes=(),
            constraints=(),
            done_when="goal_constraints_satisfied",
            abort_when=("no_capability_path",),
            planner_actions=(
                {
                    "action": "submit_job",
                    "target": {
                        "job_id": "job-1",
                        "tenant_id": "tenant-a",
                        "project_id": "project-a",
                        "queue_id": "default",
                        "submitter_id": "alice",
                        "job_type": "batch",
                        "entrypoint": "python train.py",
                    },
                },
            ),
        )

        plan = build_initial_plan(goal_spec, registry)

        self.assertEqual(plan.steps[1].capability_name, "job.submit")

    def test_planner_maps_plan_job_action_to_job_plan_capability(self):
        registry = build_platform_capability_registry(_build_state())
        goal_spec = GoalSpec(
            session_id="sess-job-plan",
            raw_message="规划作业放置",
            goal_type="runtime_control",
            permission_mode="low",
            scope_gpu_indexes=(),
            constraints=(),
            done_when="goal_constraints_satisfied",
            abort_when=("no_capability_path",),
            planner_actions=(
                {
                    "action": "plan_job",
                    "target": {
                        "job_id": "job-plan-1",
                        "tenant_id": "tenant-a",
                        "project_id": "project-a",
                        "queue_id": "default",
                        "submitter_id": "alice",
                        "job_type": "batch",
                        "entrypoint": "python train.py",
                        "resource_request": {"gpu": 1},
                    },
                },
            ),
        )

        plan = build_initial_plan(goal_spec, registry)

        self.assertEqual(plan.steps[1].capability_name, "job.plan")

    def test_planner_maps_reschedule_plan_action_to_capability(self):
        registry = build_platform_capability_registry(_build_state())
        goal_spec = GoalSpec(
            session_id="sess-reschedule",
            raw_message="重排作业 job-1",
            goal_type="runtime_control",
            permission_mode="low",
            scope_gpu_indexes=(),
            constraints=(),
            done_when="goal_constraints_satisfied",
            abort_when=("no_capability_path",),
            planner_actions=(
                {
                    "action": "plan_reschedule",
                    "target": {"job_id": "job-1"},
                },
            ),
        )

        plan = build_initial_plan(goal_spec, registry)

        self.assertEqual(plan.steps[1].capability_name, "reschedule.plan")

    def test_planner_maps_queue_reconcile_action_to_capability(self):
        registry = build_platform_capability_registry(_build_state())
        goal_spec = GoalSpec(
            session_id="sess-reconcile",
            raw_message="执行一次队列调和",
            goal_type="runtime_control",
            permission_mode="low",
            scope_gpu_indexes=(),
            constraints=(),
            done_when="goal_constraints_satisfied",
            abort_when=("no_capability_path",),
            planner_actions=(
                {"action": "reconcile_queue", "target": {}},
            ),
        )

        plan = build_initial_plan(goal_spec, registry)

        self.assertEqual(plan.steps[1].capability_name, "queue.reconcile")

    def test_planner_maps_node_and_allocation_actions(self):
        registry = build_platform_capability_registry(_build_state())
        goal_spec = GoalSpec(
            session_id="sess-node",
            raw_message="排空节点 node-a 并释放 allocation alloc-1",
            goal_type="runtime_control",
            permission_mode="low",
            scope_gpu_indexes=(),
            constraints=(),
            done_when="goal_constraints_satisfied",
            abort_when=("no_capability_path",),
            planner_actions=(
                {"action": "drain_node", "target": {"node_id": "node-a"}},
                {"action": "release_allocation", "target": {"allocation_id": "alloc-1"}},
            ),
        )

        plan = build_initial_plan(goal_spec, registry)

        self.assertEqual(plan.steps[1].capability_name, "node.drain")
        self.assertEqual(plan.steps[2].capability_name, "allocation.release")

    def test_planner_maps_requeue_and_preempt_actions(self):
        registry = build_platform_capability_registry(_build_state())
        goal_spec = GoalSpec(
            session_id="sess-job-control",
            raw_message="重新排队作业 job-1，并抢占作业 job-2",
            goal_type="runtime_control",
            permission_mode="low",
            scope_gpu_indexes=(),
            constraints=(),
            done_when="goal_constraints_satisfied",
            abort_when=("no_capability_path",),
            planner_actions=(
                {"action": "requeue_job", "target": {"job_id": "job-1"}},
                {"action": "preempt_job", "target": {"job_id": "job-2"}},
            ),
        )

        plan = build_initial_plan(goal_spec, registry)

        self.assertEqual(plan.steps[1].capability_name, "job.requeue")
        self.assertEqual(plan.steps[2].capability_name, "job.preempt")

    def test_planner_maps_checkpoint_and_restore_actions(self):
        registry = build_platform_capability_registry(_build_state())
        goal_spec = GoalSpec(
            session_id="sess-job-checkpoint",
            raw_message="给作业 job-1 做检查点并恢复",
            goal_type="runtime_control",
            permission_mode="low",
            scope_gpu_indexes=(),
            constraints=(),
            done_when="job_state_updated",
            abort_when=("no_capability_path",),
            planner_actions=(
                {"action": "checkpoint_job", "target": {"job_id": "job-1"}},
                {"action": "restore_job", "target": {"job_id": "job-1"}},
            ),
        )

        plan = build_initial_plan(goal_spec, registry)

        self.assertEqual(plan.steps[1].capability_name, "job.checkpoint")
        self.assertEqual(plan.steps[2].capability_name, "job.restore")


if __name__ == "__main__":
    unittest.main()
