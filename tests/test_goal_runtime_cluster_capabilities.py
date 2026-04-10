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
        self.assertEqual(
            registry.get("queue.status.read").definition.side_effect_level,
            "observe",
        )

    def test_low_permission_job_submit_requires_approval(self):
        registry = build_platform_capability_registry(_build_state())

        self.assertTrue(requires_approval(registry.get("job.submit").definition, "low"))

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


if __name__ == "__main__":
    unittest.main()
