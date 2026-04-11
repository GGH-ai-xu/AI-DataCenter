import asyncio
import os
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.goal_runtime.capability import CapabilityDefinition  # noqa: E402
from app.services.goal_runtime.capability_registry import CapabilityRegistry  # noqa: E402
from app.services.goal_runtime.goal_parser import parse_goal_message  # noqa: E402
from app.services.goal_runtime.goal_spec import GoalSpec  # noqa: E402
from app.services.goal_runtime.planner import build_initial_plan  # noqa: E402


class FakeImportContext:
    def __init__(self, gpu_indexes):
        self._gpu_indexes = gpu_indexes

    def selected_gpu_indexes(self):
        return list(self._gpu_indexes)


def build_test_registry():
    registry = CapabilityRegistry()
    registry.register(
        CapabilityDefinition(
            "runtime.snapshot.read",
            "runtime",
            "observe",
            False,
            ("http_local",),
        ),
        handler=lambda ctx, args: None,
    )
    registry.register(
        CapabilityDefinition(
            "scheduler.power_limit.set",
            "scheduler",
            "runtime_action",
            True,
            ("http_local",),
        ),
        handler=lambda ctx, args: None,
    )
    registry.register(
        CapabilityDefinition(
            "tasks.pause",
            "tasks",
            "runtime_action",
            True,
            ("http_local",),
        ),
        handler=lambda ctx, args: None,
    )
    registry.register(
        CapabilityDefinition(
            "scheduler.auto.configure",
            "scheduler",
            "runtime_action",
            False,
            ("http_local",),
        ),
        handler=lambda ctx, args: None,
    )
    registry.register(
        CapabilityDefinition(
            "scheduler.carbon_budget.configure",
            "scheduler",
            "runtime_action",
            False,
            ("http_local",),
        ),
        handler=lambda ctx, args: None,
    )
    registry.register(
        CapabilityDefinition(
            "job.pause",
            "jobs",
            "runtime_action",
            False,
            ("http_local",),
        ),
        handler=lambda ctx, args: None,
    )
    registry.register(
        CapabilityDefinition(
            "job.plan",
            "jobs",
            "observe",
            False,
            ("http_local",),
        ),
        handler=lambda ctx, args: None,
    )
    registry.register(
        CapabilityDefinition(
            "job.submit",
            "jobs",
            "runtime_action",
            False,
            ("http_local",),
        ),
        handler=lambda ctx, args: None,
    )
    registry.register(
        CapabilityDefinition(
            "job.requeue",
            "jobs",
            "runtime_action",
            False,
            ("http_local",),
        ),
        handler=lambda ctx, args: None,
    )
    registry.register(
        CapabilityDefinition(
            "job.preempt",
            "jobs",
            "runtime_action",
            False,
            ("http_local",),
        ),
        handler=lambda ctx, args: None,
    )
    registry.register(
        CapabilityDefinition(
            "job.checkpoint",
            "jobs",
            "runtime_action",
            False,
            ("http_local",),
        ),
        handler=lambda ctx, args: None,
    )
    registry.register(
        CapabilityDefinition(
            "job.restore",
            "jobs",
            "runtime_action",
            False,
            ("http_local",),
        ),
        handler=lambda ctx, args: None,
    )
    registry.register(
        CapabilityDefinition(
            "reschedule.plan",
            "scheduler",
            "observe",
            False,
            ("http_local",),
        ),
        handler=lambda ctx, args: None,
    )
    registry.register(
        CapabilityDefinition(
            "queue.reconcile",
            "queues",
            "runtime_action",
            False,
            ("http_local",),
        ),
        handler=lambda ctx, args: None,
    )
    registry.register(
        CapabilityDefinition(
            "node.drain",
            "nodes",
            "runtime_action",
            False,
            ("http_local",),
        ),
        handler=lambda ctx, args: None,
    )
    registry.register(
        CapabilityDefinition(
            "node.undrain",
            "nodes",
            "runtime_action",
            False,
            ("http_local",),
        ),
        handler=lambda ctx, args: None,
    )
    registry.register(
        CapabilityDefinition(
            "allocation.release",
            "allocations",
            "runtime_action",
            False,
            ("http_local",),
        ),
        handler=lambda ctx, args: None,
    )
    return registry


def test_parse_goal_message_extracts_runtime_control_constraints():
    spec = asyncio.run(
        parse_goal_message(
            session_id="sess-1",
            message="把 GPU 0 的功耗上限调到 220W，但不要影响 urgent 任务",
            permission_mode="high",
            import_context=FakeImportContext([0, 1]),
            llm_service=None,
        )
    )

    assert spec.goal_type == "runtime_control"
    assert "urgent" in " ".join(spec.constraints)
    assert spec.scope_gpu_indexes == (0, 1)


def test_build_initial_plan_prefers_read_then_runtime_actions():
    plan = build_initial_plan(
        goal_spec=GoalSpec(
            session_id="sess-1",
            raw_message="把 GPU 0 的功耗上限调到 220W",
            goal_type="runtime_control",
            permission_mode="low",
            scope_gpu_indexes=(0,),
            constraints=(),
            done_when="goal_constraints_satisfied",
            abort_when=("no_capability_path",),
        ),
        registry=build_test_registry(),
    )

    assert plan.steps[0].capability_name == "runtime.snapshot.read"
    assert plan.steps[-1].capability_name == "scheduler.power_limit.set"
    assert plan.steps[-1].fallback_capabilities == ()


def test_parse_goal_message_extracts_policy_and_job_control_actions():
    spec = asyncio.run(
        parse_goal_message(
            session_id="sess-2",
            message="关闭自动调度，把每日碳预算设为 42kg，并暂停作业 job-7",
            permission_mode="low",
            import_context=FakeImportContext([0]),
            llm_service=None,
        )
    )

    action_names = [item["action"] for item in spec.planner_actions]

    assert "configure_auto_schedule" in action_names
    assert "configure_carbon_budget" in action_names
    assert "pause_job" in action_names


def test_build_initial_plan_maps_new_policy_actions_to_capabilities():
    plan = build_initial_plan(
        goal_spec=GoalSpec(
            session_id="sess-3",
            raw_message="关闭自动调度并暂停作业 job-7",
            goal_type="runtime_control",
            permission_mode="low",
            scope_gpu_indexes=(0,),
            constraints=(),
            done_when="goal_constraints_satisfied",
            abort_when=("no_capability_path",),
            planner_actions=(
                {"action": "configure_auto_schedule", "target": {"enabled": False}},
                {"action": "pause_job", "target": {"job_id": "job-7"}},
            ),
        ),
        registry=build_test_registry(),
    )

    assert plan.steps[1].capability_name == "scheduler.auto.configure"
    assert plan.steps[2].capability_name == "job.pause"


def test_parse_goal_message_extracts_node_and_allocation_control_actions():
    spec = asyncio.run(
        parse_goal_message(
            session_id="sess-4",
            message="排空节点 node-a，并释放 allocation alloc-1",
            permission_mode="low",
            import_context=FakeImportContext([0]),
            llm_service=None,
        )
    )

    action_names = [item["action"] for item in spec.planner_actions]

    assert "drain_node" in action_names
    assert "release_allocation" in action_names


def test_parse_goal_message_extracts_checkpoint_and_restore_job_actions():
    spec = asyncio.run(
        parse_goal_message(
            session_id="sess-4b",
            message="给作业 job-9 做检查点，然后恢复 job-9",
            permission_mode="low",
            import_context=FakeImportContext([0]),
            llm_service=None,
        )
    )

    action_names = [item["action"] for item in spec.planner_actions]

    assert "checkpoint_job" in action_names
    assert "restore_job" in action_names


def test_parse_goal_message_extracts_job_planning_action():
    spec = asyncio.run(
        parse_goal_message(
            session_id="sess-6",
            message="请先规划作业 job-plan-1，使用 2 张 GPU 和 8 核 CPU 的放置方案",
            permission_mode="low",
            import_context=FakeImportContext([0, 1]),
            llm_service=None,
        )
    )

    action = next(
        item for item in spec.planner_actions if item["action"] == "plan_job"
    )

    assert action["target"]["job_id"] == "job-plan-1"
    assert action["target"]["resource_request"]["gpu"] == 2
    assert action["target"]["resource_request"]["cpu"] == 8


def test_parse_goal_message_extracts_submit_job_for_training_request():
    spec = asyncio.run(
        parse_goal_message(
            session_id="sess-submit-1",
            message="提交一个训练任务 job-train-1，使用 2 张 GPU 和 8 核 CPU，命令 python train.py",
            permission_mode="low",
            import_context=FakeImportContext([0, 1]),
            llm_service=None,
        )
    )

    action = next(
        item for item in spec.planner_actions if item["action"] == "submit_job"
    )

    assert action["target"]["job_id"] == "job-train-1"
    assert action["target"]["task_kind"] == "training"
    assert action["target"]["lifecycle_kind"] == "batch"
    assert action["target"]["resource_request"]["gpu"] == 2
    assert action["target"]["resource_request"]["cpu"] == 8


def test_submit_job_goal_flows_into_job_submit_plan_step():
    spec = asyncio.run(
        parse_goal_message(
            session_id="sess-submit-2",
            message="启动一个交互式会话 job-shell-1，使用 1 张 GPU，命令 python -m jupyter lab --port 8899",
            permission_mode="low",
            import_context=FakeImportContext([0, 1]),
            llm_service=None,
        )
    )

    plan = build_initial_plan(
        goal_spec=spec,
        registry=build_test_registry(),
    )

    submit_step = next(
        step for step in plan.steps if step.capability_name == "job.submit"
    )

    assert submit_step.arguments["job_id"] == "job-shell-1"
    assert submit_step.arguments["task_kind"] == "interactive_session"
    assert submit_step.arguments["lifecycle_kind"] == "session"


def test_parse_goal_message_extracts_reschedule_planning_action():
    spec = asyncio.run(
        parse_goal_message(
            session_id="sess-7",
            message="请先重排作业 job-7，看看更适合放到哪里",
            permission_mode="low",
            import_context=FakeImportContext([0]),
            llm_service=None,
        )
    )

    action = next(
        item for item in spec.planner_actions if item["action"] == "plan_reschedule"
    )

    assert action["target"]["job_id"] == "job-7"


def test_parse_goal_message_extracts_queue_reconcile_action():
    spec = asyncio.run(
        parse_goal_message(
            session_id="sess-7b",
            message="执行一次队列调和，把等待作业推进下去",
            permission_mode="low",
            import_context=FakeImportContext([0]),
            llm_service=None,
        )
    )

    action = next(
        item for item in spec.planner_actions if item["action"] == "reconcile_queue"
    )

    assert action["target"] == {}


def test_build_initial_plan_maps_node_and_allocation_actions_to_capabilities():
    plan = build_initial_plan(
        goal_spec=GoalSpec(
            session_id="sess-5",
            raw_message="排空节点 node-a，并释放 allocation alloc-1",
            goal_type="runtime_control",
            permission_mode="low",
            scope_gpu_indexes=(0,),
            constraints=(),
            done_when="goal_constraints_satisfied",
            abort_when=("no_capability_path",),
            planner_actions=(
                {"action": "drain_node", "target": {"node_id": "node-a"}},
                {"action": "release_allocation", "target": {"allocation_id": "alloc-1"}},
            ),
        ),
        registry=build_test_registry(),
    )

    assert plan.steps[1].capability_name == "node.drain"
    assert plan.steps[2].capability_name == "allocation.release"


def test_build_initial_plan_maps_job_planning_actions_to_capabilities():
    plan = build_initial_plan(
        goal_spec=GoalSpec(
            session_id="sess-8",
            raw_message="规划作业与重排作业",
            goal_type="runtime_control",
            permission_mode="low",
            scope_gpu_indexes=(0,),
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
                {"action": "plan_reschedule", "target": {"job_id": "job-7"}},
            ),
        ),
        registry=build_test_registry(),
    )

    assert plan.steps[1].capability_name == "job.plan"
    assert plan.steps[2].capability_name == "reschedule.plan"


def test_build_initial_plan_maps_queue_reconcile_to_capability():
    plan = build_initial_plan(
        goal_spec=GoalSpec(
            session_id="sess-9",
            raw_message="执行队列调和",
            goal_type="runtime_control",
            permission_mode="low",
            scope_gpu_indexes=(0,),
            constraints=(),
            done_when="goal_constraints_satisfied",
            abort_when=("no_capability_path",),
            planner_actions=(
                {"action": "reconcile_queue", "target": {}},
            ),
        ),
        registry=build_test_registry(),
    )

    assert plan.steps[1].capability_name == "queue.reconcile"


def test_parse_goal_message_extracts_requeue_and_preempt_job_actions():
    spec = asyncio.run(
        parse_goal_message(
            session_id="sess-10",
            message="把作业 job-7 重新排队，并抢占作业 job-8",
            permission_mode="low",
            import_context=FakeImportContext([0]),
            llm_service=None,
        )
    )

    action_names = [item["action"] for item in spec.planner_actions]

    assert "requeue_job" in action_names
    assert "preempt_job" in action_names


def test_build_initial_plan_maps_requeue_and_preempt_to_job_control_capabilities():
    plan = build_initial_plan(
        goal_spec=GoalSpec(
            session_id="sess-11",
            raw_message="重新排队作业并抢占作业",
            goal_type="runtime_control",
            permission_mode="low",
            scope_gpu_indexes=(0,),
            constraints=(),
            done_when="goal_constraints_satisfied",
            abort_when=("no_capability_path",),
            planner_actions=(
                {"action": "requeue_job", "target": {"job_id": "job-7"}},
                {"action": "preempt_job", "target": {"job_id": "job-8"}},
            ),
        ),
        registry=build_test_registry(),
    )

    assert plan.steps[1].capability_name == "job.requeue"
    assert plan.steps[2].capability_name == "job.preempt"


def test_build_initial_plan_maps_checkpoint_and_restore_to_job_control_capabilities():
    plan = build_initial_plan(
        goal_spec=GoalSpec(
            session_id="sess-12",
            raw_message="给作业做检查点并恢复",
            goal_type="runtime_control",
            permission_mode="low",
            scope_gpu_indexes=(0,),
            constraints=(),
            done_when="job_state_updated",
            abort_when=("no_capability_path",),
            planner_actions=(
                {"action": "checkpoint_job", "target": {"job_id": "job-7"}},
                {"action": "restore_job", "target": {"job_id": "job-7"}},
            ),
        ),
        registry=build_test_registry(),
    )

    assert plan.steps[1].capability_name == "job.checkpoint"
    assert plan.steps[2].capability_name == "job.restore"
