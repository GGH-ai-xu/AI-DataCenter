import json
import os
import sys
import types
import unittest
from unittest import mock

from fastapi import HTTPException


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.api import graph as graph_api
from app.models.graph_schemas import GraphStrategyRequest
from app.services.graph_strategy import (
    build_graph_strategy_context,
    build_graph_strategy_fallback,
)


def _mixed_graph_view():
    return {
        "nodes": [
            {
                "id": "paper_1",
                "label": "Paper",
                "name": "Self-RAG",
                "paper_title": "Self-RAG",
                "description": "paper node",
                "source": "paper",
            },
            {
                "id": "strategy_1",
                "label": "OptimizationStrategy",
                "name": "高峰限功调度",
                "paper_title": "绿算生金优化本体",
                "description": "高峰期优先降低低负载 GPU 功率。",
                "source": "optimization",
            },
            {
                "id": "constraint_1",
                "label": "Constraint",
                "name": "紧急任务不可暂停",
                "paper_title": "绿算生金优化本体",
                "description": "urgent 任务不能被暂停。",
                "source": "optimization",
            },
            {
                "id": "metric_1",
                "label": "Metric",
                "name": "总功耗",
                "paper_title": "绿算生金优化本体",
                "description": "核心能耗指标。",
                "source": "optimization",
            },
            {
                "id": "template_1",
                "label": "CodeTemplate",
                "name": "scheduler_power_guard",
                "paper_title": "绿算生金优化本体",
                "description": "保护紧急任务前提下执行限功策略的模板。",
                "source": "optimization",
            },
            {
                "id": "api_1",
                "label": "API",
                "name": "set_power_limit",
                "paper_title": "绿算生金优化本体",
                "description": "限功接口。",
                "source": "optimization",
            },
            {
                "id": "api_2",
                "label": "API",
                "name": "run_schedule_once",
                "paper_title": "绿算生金优化本体",
                "description": "调度接口。",
                "source": "optimization",
            },
        ],
        "relationships": [
            {
                "id": "rel_1",
                "source_id": "strategy_1",
                "target_id": "constraint_1",
                "type": "REQUIRES",
                "description": "策略必须满足紧急任务保护。",
                "paper_title": "绿算生金优化本体",
            },
            {
                "id": "rel_2",
                "source_id": "strategy_1",
                "target_id": "metric_1",
                "type": "OPTIMIZES",
                "description": "策略目标是降低总功耗。",
                "paper_title": "绿算生金优化本体",
            },
            {
                "id": "rel_3",
                "source_id": "strategy_1",
                "target_id": "template_1",
                "type": "USES_TEMPLATE",
                "description": "策略依赖模板。",
                "paper_title": "绿算生金优化本体",
            },
            {
                "id": "rel_4",
                "source_id": "template_1",
                "target_id": "api_1",
                "type": "CALLS_API",
                "description": "模板会调用限功接口。",
                "paper_title": "绿算生金优化本体",
            },
            {
                "id": "rel_5",
                "source_id": "template_1",
                "target_id": "api_2",
                "type": "CALLS_API",
                "description": "模板会调用调度接口。",
                "paper_title": "绿算生金优化本体",
            },
        ],
        "label_counts": {
            "Paper": 1,
            "OptimizationStrategy": 1,
            "Constraint": 1,
            "Metric": 1,
            "CodeTemplate": 1,
            "API": 2,
        },
        "relation_type_counts": {
            "REQUIRES": 1,
            "OPTIMIZES": 1,
            "USES_TEMPLATE": 1,
            "CALLS_API": 2,
        },
    }


def _control_context():
    return {
        "llm_context": json.dumps({
            "time_period": "高峰期",
            "budget": {
                "enabled": True,
                "total_power_budget": 1200,
            },
            "gpus": [
                {
                    "index": 0,
                    "power_usage": 280.0,
                    "gpu_utilization": 25,
                    "temperature": 72,
                },
                {
                    "index": 1,
                    "power_usage": 300.0,
                    "gpu_utilization": 84,
                    "temperature": 79,
                },
            ],
            "manageable_processes": [
                {"pid": 1234, "priority": "urgent"},
                {"pid": 5678, "priority": "deferrable"},
            ],
        }, ensure_ascii=False),
    }


def test_build_graph_strategy_context_prefers_optimization_nodes():
    context = build_graph_strategy_context(
        "高峰期降低总功耗，但不影响紧急任务",
        _mixed_graph_view(),
        _control_context(),
        max_nodes=8,
        max_relationships=8,
    )

    node_labels = {node["label"] for node in context["evidence_nodes"]}

    assert "Paper" not in node_labels
    assert "OptimizationStrategy" in node_labels
    assert "Constraint" in node_labels
    assert context["focus"]["strategies"] == ["高峰限功调度"]
    assert "高峰期" in context["runtime_summary"]


def test_build_graph_strategy_fallback_returns_code_and_control_prompt():
    context = build_graph_strategy_context(
        "高峰期降低总功耗，但不影响紧急任务",
        _mixed_graph_view(),
        _control_context(),
        max_nodes=8,
        max_relationships=8,
    )
    fallback = build_graph_strategy_fallback(
        "高峰期降低总功耗，但不影响紧急任务",
        context,
    )

    assert "高峰限功调度" in fallback["summary"]
    assert len(fallback["strategy_steps"]) >= 4
    assert "set_power_limit" in fallback["code_snippet"]
    assert "run_schedule_once" in fallback["code_snippet"]
    assert "保守优化" in fallback["control_prompt"]
    assert fallback["evidence"]


class FakeGraphApiGraph:
    async def view_graph(self, query="", limit=180):
        return {
            "ok": True,
            "configured": True,
            "neo4j_connected": True,
            **_mixed_graph_view(),
        }


class FakeGraphApiAgent:
    async def get_all_gpus(self):
        return [
            {
                "index": 0,
                "name": "RTX 3090",
                "temperature": 72,
                "power_usage": 280.0,
                "power_limit": 320.0,
                "gpu_utilization": 25,
                "memory_used": 12000,
                "memory_total": 24576,
            },
            {
                "index": 1,
                "name": "RTX 3090",
                "temperature": 79,
                "power_usage": 300.0,
                "power_limit": 320.0,
                "gpu_utilization": 84,
                "memory_used": 18000,
                "memory_total": 24576,
            },
        ]

    async def get_processes(self):
        return [
            {
                "pid": 1234,
                "gpu_index": 0,
                "name": "train-a",
                "username": "alice",
                "priority": "urgent",
                "gpu_memory_used": 4000,
                "manageable_reason": "",
                "command": "python train_a.py",
            },
            {
                "pid": 5678,
                "gpu_index": 1,
                "name": "train-b",
                "username": "bob",
                "priority": "deferrable",
                "gpu_memory_used": 6000,
                "manageable_reason": "",
                "command": "python train_b.py",
            },
        ]


class FakeGraphApiImportContext:
    def filter_gpus(self, gpus):
        return gpus

    def filter_processes(self, processes):
        return processes


class FakeGraphApiPrivacy:
    def sanitize_processes(self, processes):
        return processes


class FakeGraphApiStore:
    async def get_all_task_priorities(self):
        return {
            1234: "urgent",
            5678: "deferrable",
        }


class FakeGraphApiScheduler:
    def get_budget_status(self, _gpus):
        return {
            "enabled": True,
            "total_power_budget": 1200,
        }


class FakeGraphApiLLM:
    def __init__(self, result=None):
        self.result = result or {
            "summary": "建议走高峰限功调度",
            "strategy_steps": ["保护紧急任务", "限制低利用率 GPU 功耗", "执行一次综合调度"],
            "control_prompt": "保护紧急任务后，对低利用率 GPU 小步限功到 220W 并执行综合调度。",
            "code_title": "scheduler_power_guard",
            "code_language": "python",
            "code_snippet": "def scheduler_power_guard():\n    run_schedule_once()",
            "risk_notice": "执行前需核对当前预算和任务优先级。",
            "evidence": ["OptimizationStrategy: 高峰限功调度"],
            "follow_ups": ["还有哪些约束需要满足？"],
        }
        self.calls = []

    async def generate_graph_strategy_plan(
        self,
        goal,
        graph_context_text,
        runtime_context_text,
    ):
        self.calls.append((goal, graph_context_text, runtime_context_text))
        return dict(self.result)


class GraphStrategyRouteTests(unittest.IsolatedAsyncioTestCase):
    def test_graph_api_exposes_strategy_route_handler(self):
        self.assertTrue(hasattr(graph_api, "generate_graph_strategy"))

    async def test_strategy_route_returns_llm_payload(self):
        fake_llm = FakeGraphApiLLM()
        fake_state = types.SimpleNamespace(
            graph=FakeGraphApiGraph(),
            llm=fake_llm,
            agent=FakeGraphApiAgent(),
            import_context=FakeGraphApiImportContext(),
            privacy=FakeGraphApiPrivacy(),
            store=FakeGraphApiStore(),
            scheduler=FakeGraphApiScheduler(),
        )
        fake_main = types.SimpleNamespace(app_state=fake_state)
        request = types.SimpleNamespace(state=types.SimpleNamespace(user={"role": "member"}))

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            result = await graph_api.generate_graph_strategy(
                request,
                GraphStrategyRequest(message="高峰期降低总功耗，但不影响紧急任务"),
            )

        self.assertEqual(result["message"], "高峰期降低总功耗，但不影响紧急任务")
        self.assertTrue(result["used_llm"])
        self.assertEqual(result["code_title"], "scheduler_power_guard")
        self.assertIn("高峰期", fake_llm.calls[0][2])
        self.assertIn("OptimizationStrategy", fake_llm.calls[0][1])

    async def test_strategy_route_falls_back_without_llm(self):
        fake_state = types.SimpleNamespace(
            graph=FakeGraphApiGraph(),
            llm=None,
            agent=FakeGraphApiAgent(),
            import_context=FakeGraphApiImportContext(),
            privacy=FakeGraphApiPrivacy(),
            store=FakeGraphApiStore(),
            scheduler=FakeGraphApiScheduler(),
        )
        fake_main = types.SimpleNamespace(app_state=fake_state)
        request = types.SimpleNamespace(state=types.SimpleNamespace(user={"role": "member"}))

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            result = await graph_api.generate_graph_strategy(
                request,
                GraphStrategyRequest(message="高峰期降低总功耗，但不影响紧急任务"),
            )

        self.assertFalse(result["used_llm"])
        self.assertTrue(result["strategy_steps"])
        self.assertIn("保守优化", result["control_prompt"])

    async def test_strategy_route_rejects_blank_goal(self):
        fake_state = types.SimpleNamespace(
            graph=FakeGraphApiGraph(),
            llm=None,
            agent=FakeGraphApiAgent(),
            import_context=FakeGraphApiImportContext(),
            privacy=FakeGraphApiPrivacy(),
            store=FakeGraphApiStore(),
            scheduler=FakeGraphApiScheduler(),
        )
        fake_main = types.SimpleNamespace(app_state=fake_state)
        request = types.SimpleNamespace(state=types.SimpleNamespace(user={"role": "member"}))

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            with self.assertRaises(HTTPException) as ctx:
                await graph_api.generate_graph_strategy(
                    request,
                    GraphStrategyRequest(message=" "),
                )

        self.assertEqual(ctx.exception.status_code, 400)
