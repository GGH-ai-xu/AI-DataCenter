from __future__ import annotations


def build_testing_detail() -> dict:
    return {
        "agent_effectiveness": {
            "endpoint_groups": [
                {"name": "采集接口", "value": 7},
                {"name": "控制接口", "value": 4},
                {"name": "运行时接口", "value": 10},
            ],
            "telemetry_fields": [
                "temperature",
                "power_usage",
                "power_limit",
                "gpu_utilization",
                "memory_used",
                "memory_total",
                "fan_speed",
                "clock_sm",
                "clock_mem",
                "timestamp",
            ],
            "sampling": {
                "cached_accesses": 3,
                "real_scans": 2,
                "cache_hits": 1,
                "cpu_sampling": "interval=None/0",
            },
            "real_checks": {
                "passed": 21,
                "duration_sec": 0.73,
                "files": [
                    "tests/test_agent_sampling_structure.py",
                    "tests/test_monitor_api.py",
                    "tests/test_agent_startup_logging.py",
                    "tests/test_cluster_job_api.py",
                    "backend/tests/test_graph_store_view.py",
                ],
            },
            "integration_points": [
                {
                    "name": "远程 Provider 兼容",
                    "detail": "system-detail 路由可透过 HttpAgentProvider 读取远程系统详情",
                    "state": "passed",
                },
                {
                    "name": "导入后训练日志过滤",
                    "detail": "training 路由只保留 imported GPUs 对应日志",
                    "state": "passed",
                },
                {
                    "name": "缺失 NVML 时明确提示",
                    "detail": "启动日志不会伪造 GPU 结果，而是给出 SSH Linux / 远程 Agent 提示",
                    "state": "passed",
                },
                {
                    "name": "进程缓存采样",
                    "detail": "连续 3 次读取仅触发 2 次真实扫描，降低采样阻塞",
                    "state": "passed",
                },
            ],
        },
        "extension_validation": {
            "stable": [
                {"name": "Agent / Monitor / Cluster / Graph", "passed": 21, "duration_sec": 0.73},
                {"name": "Agent Runtime API", "passed": 3, "duration_sec": 0.38},
            ],
            "drift": [
                {
                    "name": "tests/test_goal_runtime_api.py",
                    "kind": "collection_error",
                    "reason": "append_agent_runtime_chat_turn 与现有 agent_runtime.py 接口不一致",
                },
                {
                    "name": "backend/tests/test_ai_control.py",
                    "kind": "collection_error",
                    "reason": "SUPPORTED_ACTIONS 与现有 control_heuristics 接口不一致",
                },
            ],
        },
    }
