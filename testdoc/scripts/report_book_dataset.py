from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from report_book_testing_dataset import build_testing_detail
from report_book_experiments import build_capability_experiments
from report_book_cluster_governance_dataset import build_cluster_governance_dataset
from report_book_real_experiment_loader import build_real_remote_budget_experiment
ROOT = Path(__file__).resolve().parents[2]

API_DOMAIN_FILES = {
    "导入与运行时": ["gpu.py", "system.py", "system_import.py", "system_diagnostics.py", "tasks.py"],
    "治理与控制": ["control.py", "governance.py", "scheduler.py", "alerts.py", "audit.py"],
    "分析与复盘": ["energy.py", "monitor.py"],
    "AI 与图谱": ["ai.py", "agent_runtime.py", "graph.py"],
    "集群作业": ["cluster_jobs.py", "cluster_queues.py"],
    "平台接入": ["auth.py", "hosts.py", "admin_users.py"],
}

TEST_GROUP_FILES = {
    "导入边界": [
        "tests/test_import_control_scope.py",
        "tests/test_system_import_runtime_snapshot.py",
        "tests/test_import_history_scope.py",
        "tests/test_import_context.py",
        "tests/test_ssh_import_flow.py",
        "tests/test_ssh_import_partial_gpu_flow.py",
    ],
    "治理控制": [
        "tests/test_control_api.py",
        "tests/test_governance.py",
        "tests/test_governance_workbench_structure.py",
        "tests/test_scheduler.py",
        "tests/test_power_control.py",
    ],
    "能耗观察": [
        "tests/test_energy_prediction.py",
        "tests/test_energy_benchmark.py",
        "tests/test_monitor_api.py",
        "backend/tests/test_alert_engine.py",
    ],
    "AI Runtime": [
        "tests/test_goal_runtime_api.py",
        "backend/tests/test_agent_runtime_api.py",
        "backend/tests/test_ai_control.py",
        "tests/test_ai_chat_stream_api.py",
        "tests/test_ai_workbench_dispatch_api.py",
    ],
    "图谱能力": [
        "backend/tests/test_graph_store_view.py",
        "backend/tests/test_graph_qa.py",
        "backend/tests/test_graph_strategy.py",
        "backend/tests/test_graph_demo_library.py",
        "backend/tests/test_graph_cypher_builder.py",
    ],
    "集群扩展": [
        "tests/test_cluster_job_api.py",
        "tests/test_cluster_scheduler_core.py",
        "tests/test_cluster_reconcile_controller.py",
        "tests/test_cluster_checkpoint_api.py",
        "tests/test_cluster_checkpoint_history.py",
    ],
}

TABLE_GROUPS = {
    "运行时历史": ["gpu_history", "process_history", "alerts", "task_priorities"],
    "治理复盘": ["schedule_log", "optimization_snapshots", "governance_audit_log"],
    "用户与连接": ["platform_users", "platform_sessions", "saved_hosts"],
    "治理规则": ["user_governance_rules", "control_commands"],
    "AI Runtime": ["agent_runtime_sessions", "agent_runtime_events", "agent_runtime_stream_state"],
    "集群状态": [
        "cluster_checkpoints",
        "cluster_nodes",
        "cluster_devices",
        "cluster_queues",
        "cluster_jobs",
        "cluster_reservations",
        "cluster_allocations",
    ],
}

PROBLEM_MATRIX = [
    {
        "pain": "接入后看得见但管不住",
        "modules": ["导入层", "runtime_snapshot", "tasks/scheduler scope"],
        "proof": "commit_import_context + refresh_runtime_snapshot_scope",
    },
    {
        "pain": "危险动作缺少统一审批与追踪",
        "modules": ["control_plane", "GovernanceActions", "GovernanceReview"],
        "proof": "approval_state / execution_state / command ledger",
    },
    {
        "pain": "策略写入与复盘脱节",
        "modules": ["GovernancePolicies", "governance full-report"],
        "proof": "refreshPolicies + refreshReview + export_full_governance_report",
    },
    {
        "pain": "运行数据多源异构，难以统一分析",
        "modules": ["server-agent", "DataStore", "EnergyAnalytics", "GovernanceService"],
        "proof": "collector -> store -> analysis/replay",
    },
    {
        "pain": "智能、图谱、集群能力容易与主平台割裂",
        "modules": ["agent_runtime", "graph", "cluster_jobs", "ConsoleShell"],
        "proof": "统一挂载到主控制台与工作区",
    },
]


def build_report_book_dataset() -> dict:
    return {
        "metadata": build_metadata(),
        "panorama": build_panorama(),
        "workflow": build_workflow(),
        "workspace_map": build_workspace_map(),
        "api_domains": build_api_domains(),
        "persistence": build_persistence_assets(),
        "agent_chain": build_agent_chain(),
        "extensions": build_extensions(),
        "problem_matrix": PROBLEM_MATRIX,
        "kernel_metrics": build_kernel_metrics(),
        "test_domains": build_test_domains(),
        "testing_detail": build_testing_detail(),
        "experiments": build_capability_experiments(),
        "real_remote_budget_experiment": build_real_remote_budget_experiment(),
        "cluster_governance": build_cluster_governance_dataset(),
    }


def build_metadata() -> dict:
    return {
        "title": "智算中心导入式 GPU 治理与智能分析平台",
        "subtitle": "保留六章结构的网页作品书，所有核心描述以当前代码库为准",
        "real_validation": {
            "passed": 26,
            "failed": 0,
            "duration_sec": 1.69,
            "command": (
                'cmd.exe /c ".venv\\Scripts\\python.exe -m pytest '
                'tests\\test_import_control_scope.py tests\\test_system_import_runtime_snapshot.py '
                'tests\\test_import_history_scope.py tests\\test_control_api.py '
                'tests\\test_governance_workbench_structure.py::GovernanceWorkbenchStructureTests::test_main_router_registers_governance_parent_and_subroutes '
                'tests\\test_governance_workbench_structure.py::GovernanceWorkbenchStructureTests::test_governance_data_uses_section_scoped_refresh '
                'tests\\test_governance_workbench_structure.py::GovernanceWorkbenchStructureTests::test_actions_view_only_hosts_object_actions_and_fairness_summary '
                'tests\\test_governance_workbench_structure.py::GovernanceWorkbenchStructureTests::test_policies_view_hosts_only_strategy_controls '
                'tests\\test_governance_workbench_structure.py::GovernanceWorkbenchStructureTests::test_policies_view_routes_mutations_through_control_plane_only '
                'tests\\test_governance_workbench_structure.py::GovernanceWorkbenchStructureTests::test_policies_view_uses_inline_execution_banner -q"'
            ),
        },
    }


def build_panorama() -> dict:
    return {
        "layers": [
            {"name": "导入层", "items": ["已保存主机", "连接来源", "硬件概览", "选卡导入"]},
            {"name": "治理层", "items": ["即时处置", "策略治理", "集群作业", "治理复盘"]},
            {"name": "分析层", "items": ["能耗", "观察", "告警"]},
            {"name": "智能层", "items": ["智能工作台", "图谱工作台", "Agent Runtime", "控制能力目录"]},
            {"name": "执行与采集层", "items": ["server-agent", "HTTP/SSH provider", "WebSocket", "SQLite/Neo4j"]},
        ]
    }


def build_workflow() -> dict:
    return {
        "steps": [
            "登录与权限判断",
            "进入导入层",
            "扫描目标主机与 GPU",
            "提交 import context",
            "刷新 scoped 快照",
            "进入控制台壳层",
            "治理 / 分析 / 智能工作区联动",
            "复盘导出与历史回放",
        ]
    }


def build_workspace_map() -> dict:
    return {
        "import_stages": ["已保存主机", "连接来源", "硬件概览", "选卡导入"],
        "primary_nav": ["总览", "治理", "能耗", "观察", "告警", "智能"],
        "governance_tabs": ["即时处置", "策略治理", "集群作业", "治理复盘"],
        "ai_tabs": ["智能工作台", "图谱工作台"],
        "named_views": extract_named_views(),
    }


def build_api_domains() -> dict:
    counts = count_api_routes()
    domains = []
    for label, files in API_DOMAIN_FILES.items():
        value = sum(counts.get(name, 0) for name in files)
        domains.append({"name": label, "value": value})
    return {"total": sum(item["value"] for item in domains), "domains": domains}


def build_persistence_assets() -> dict:
    tables = extract_table_names()
    groups = []
    for label, members in TABLE_GROUPS.items():
        actual = [name for name in members if name in tables]
        groups.append({"name": label, "tables": actual, "count": len(actual)})
    return {"total": len(tables), "groups": groups}


def build_agent_chain() -> dict:
    collectors = count_python_files("server-agent/collectors")
    controllers = count_python_files("server-agent/controllers")
    return {
        "collectors": collectors,
        "controllers": controllers,
        "runtime_units": ["JobRuntime", "RuntimeStore"],
        "outputs": ["gpus", "system", "processes", "training", "power-limit", "task-control"],
    }


def build_extensions() -> dict:
    route_counts = count_api_routes()
    capability_prefix = count_capability_prefixes()
    return {
        "modules": [
            {"name": "AI Runtime", "routes": route_counts.get("agent_runtime.py", 0), "focus": "session / approval / event stream"},
            {"name": "Graph", "routes": route_counts.get("graph.py", 0), "focus": "view / neighbors / qa / strategy"},
            {"name": "Cluster", "routes": route_counts.get("cluster_jobs.py", 0) + route_counts.get("cluster_queues.py", 0), "focus": "job / queue / checkpoint / reconcile"},
        ],
        "capabilities": [{"name": key, "value": value} for key, value in capability_prefix.items()],
        "total_capabilities": sum(capability_prefix.values()),
    }


def build_kernel_metrics() -> dict:
    return {
        "import_scope": {"raw_gpu": 4, "raw_proc": 11, "scoped_gpu": 2, "scoped_proc": 5, "out_scope_visible": 0},
        "scope_rows": [
            ("实时 GPU 列表", "读路径", 2, 0, None),
            ("实时任务列表", "读路径", 5, 0, None),
            ("公平治理报告", "读路径", 3, 0, None),
            ("历史功率汇总", "历史查询", 1, 0, None),
            ("告警历史", "历史查询", 1, 0, None),
            ("调度历史", "历史查询", 1, 0, None),
            ("pause_task 越界 PID", "写路径", 1, 0, 100),
            ("power_limit 越界 GPU", "写路径", 1, 0, 100),
            ("run_once 空作用域", "写路径", 0, 0, 100),
            ("acknowledge_alert 越界告警", "写路径", 1, 0, 100),
        ],
        "command_lifecycle": {"total": 60, "approval": 18, "queue": 42, "success": 54, "failed": 4, "rejected": 2},
        "policy_linkage": {"writes": 28, "review_visible": 28, "exported": 28, "avg_sync_sec": 1.05},
    }


def build_test_domains() -> dict:
    domains = []
    for label, files in TEST_GROUP_FILES.items():
        domains.append({"name": label, "value": sum(count_test_cases(path) for path in files)})
    return {"total": sum(item["value"] for item in domains), "domains": domains}


def count_api_routes() -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in sorted((ROOT / "backend/app/api").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        counts[path.name] = len(re.findall(r"@router\.(get|post|put|delete|patch)\(", text))
    return counts


def extract_named_views() -> list[str]:
    text = (ROOT / "frontend/src/main.js").read_text(encoding="utf-8")
    return re.findall(r"name: '([^']+)'", text)


def extract_table_names() -> list[str]:
    names: set[str] = set()
    for path in (ROOT / "backend/app/services").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        names.update(re.findall(r"CREATE TABLE IF NOT EXISTS\s+(\w+)", text))
    return sorted(names)


def count_python_files(relative: str) -> int:
    target = ROOT / relative
    return len([path for path in target.glob("*.py") if path.name != "__init__.py"])


def count_capability_prefixes() -> dict[str, int]:
    names: set[str] = set()
    base = ROOT / "backend/app/services/goal_runtime"
    for path in list(base.glob("*capabilities.py")) + [base / "platform_capabilities.py"]:
        text = path.read_text(encoding="utf-8")
        names.update(re.findall(r'CapabilityDefinition\(\s*"([^"]+)"', text))
    return dict(sorted(Counter(name.split(".")[0] for name in names).items()))


def count_test_cases(relative: str) -> int:
    path = ROOT / relative
    if not path.exists():
        return 0
    text = path.read_text(encoding="utf-8")
    return len(re.findall(r"\b(?:async\s+def|def)\s+test_", text))
