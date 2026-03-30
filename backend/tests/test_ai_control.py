"""ai_control 核心逻辑单元测试 - 规则解析与动作验证"""

import pytest
from app.services.ai_control import (
    SUPPORTED_ACTIONS,
    HIGH_RISK_ACTIONS,
    _to_int,
    _priority_from_text,
    _priority_label,
    _action_label,
    _risk_level_for_action,
    _merge_risk_levels,
    _find_pid,
    _find_gpu_index,
    _find_power_limit,
    _find_budget_value,
    _enrich_action,
    _build_heuristic_plan,
)


# ─── 基础工具函数 ────────────────────────────────────────

class TestToInt:
    def test_normal(self):
        assert _to_int(42) == 42
        assert _to_int("123") == 123

    def test_invalid(self):
        assert _to_int(None, -1) == -1
        assert _to_int("abc", 0) == 0
        assert _to_int("", 5) == 5


class TestPriorityFromText:
    def test_chinese(self):
        assert _priority_from_text("紧急任务") == "urgent"
        assert _priority_from_text("可延迟") == "deferrable"
        assert _priority_from_text("普通") == "normal"

    def test_english(self):
        assert _priority_from_text("urgent") == "urgent"
        assert _priority_from_text("deferrable") == "deferrable"
        assert _priority_from_text("Normal") == "normal"

    def test_unknown(self):
        assert _priority_from_text("") is None
        assert _priority_from_text("random") is None


class TestPriorityLabel:
    def test_known(self):
        assert _priority_label("urgent") == "紧急"
        assert _priority_label("normal") == "普通"
        assert _priority_label("deferrable") == "可延迟"

    def test_unknown(self):
        assert _priority_label(None) == "未知"


class TestActionLabel:
    def test_all_actions(self):
        for action in SUPPORTED_ACTIONS:
            label = _action_label(action)
            assert isinstance(label, str) and len(label) > 0


class TestRiskLevel:
    def test_high_risk(self):
        assert _risk_level_for_action("terminate_task") == "high"

    def test_medium_risk(self):
        assert _risk_level_for_action("set_power_limit") == "medium"
        assert _risk_level_for_action("pause_task") == "medium"

    def test_low_risk(self):
        assert _risk_level_for_action("unknown_action") == "low"

    def test_merge(self):
        assert _merge_risk_levels(["low", "medium"]) == "medium"
        assert _merge_risk_levels(["low", "high"]) == "high"
        assert _merge_risk_levels(["low", "low"]) == "low"
        assert _merge_risk_levels([]) == "low"


# ─── 自然语言提取函数 ──────────────────────────────────────

class TestFindPid:
    def test_chinese(self):
        assert _find_pid("暂停进程：12345") == 12345
        assert _find_pid("PID 6789") == 6789

    def test_standalone_number(self):
        assert _find_pid("暂停 12345 这个进程") == 12345

    def test_no_pid(self):
        assert _find_pid("暂停所有任务") is None
        assert _find_pid("") is None


class TestFindGpuIndex:
    def test_english(self):
        assert _find_gpu_index("GPU 0") == 0
        assert _find_gpu_index("gpu:1") == 1

    def test_chinese(self):
        assert _find_gpu_index("显卡 2") == 2

    def test_no_match(self):
        assert _find_gpu_index("no gpu here") is None


class TestFindPowerLimit:
    def test_watts_english(self):
        assert _find_power_limit("设到250W") == 250
        assert _find_power_limit("power 200w") == 200

    def test_watts_chinese(self):
        assert _find_power_limit("设到300瓦") == 300

    def test_no_match(self):
        assert _find_power_limit("设到50W") is None  # 50W 不是三位数


class TestFindBudgetValue:
    def test_chinese_budget(self):
        assert _find_budget_value("总功率预算设为1200W") == 1200
        assert _find_budget_value("预算 800 瓦") == 800

    def test_no_match(self):
        assert _find_budget_value("随便设一下") is None


# ─── 动作验证 _enrich_action ───────────────────────────────

def _make_context(gpus=None, processes=None):
    """构造测试用的 context 字典"""
    gpus = gpus or [
        {"index": 0, "name": "RTX 3090", "power_usage": 250, "power_limit": 350,
         "gpu_utilization": 80, "memory_used": 8000, "memory_total": 24000},
    ]
    processes = processes or [
        {"pid": 1234, "gpu_index": 0, "name": "train.py", "username": "user1",
         "gpu_memory_used": 4000, "priority": "normal", "manageable": True,
         "manageable_reason": ""},
    ]
    return {
        "gpus": gpus,
        "processes": processes,
        "process_map": {p["pid"]: p for p in processes},
        "gpu_map": {g["index"]: g for g in gpus},
        "budget": {},
    }


class TestEnrichAction:
    def test_valid_power_limit(self):
        ctx = _make_context()
        result = _enrich_action(
            {"action": "set_power_limit", "target": {"gpu_index": 0, "power_limit": 200}, "reason": "降频"},
            ctx,
        )
        assert result["valid"] is True
        assert result["risk_level"] == "medium"

    def test_invalid_gpu_index(self):
        ctx = _make_context()
        result = _enrich_action(
            {"action": "set_power_limit", "target": {"gpu_index": 9, "power_limit": 200}, "reason": ""},
            ctx,
        )
        assert result["valid"] is False
        assert "不存在" in result["blocked_reason"]

    def test_power_limit_out_of_range(self):
        ctx = _make_context()
        result = _enrich_action(
            {"action": "set_power_limit", "target": {"gpu_index": 0, "power_limit": 50}, "reason": ""},
            ctx,
        )
        assert result["valid"] is False

    def test_valid_pause_task(self):
        ctx = _make_context()
        result = _enrich_action(
            {"action": "pause_task", "target": {"pid": 1234}, "reason": "暂停"},
            ctx,
        )
        assert result["valid"] is True

    def test_invalid_pid(self):
        ctx = _make_context()
        result = _enrich_action(
            {"action": "pause_task", "target": {"pid": 9999}, "reason": ""},
            ctx,
        )
        assert result["valid"] is False
        assert "不在" in result["blocked_reason"]

    def test_unsupported_action(self):
        ctx = _make_context()
        result = _enrich_action(
            {"action": "reboot_system", "target": {}, "reason": ""},
            ctx,
        )
        assert result["valid"] is False
        assert "不受支持" in result["blocked_reason"]

    def test_terminate_is_high_risk(self):
        ctx = _make_context()
        result = _enrich_action(
            {"action": "terminate_task", "target": {"pid": 1234}, "reason": ""},
            ctx,
        )
        assert result["risk_level"] == "high"

    def test_set_priority_valid(self):
        ctx = _make_context()
        result = _enrich_action(
            {"action": "set_task_priority", "target": {"pid": 1234, "priority": "urgent"}, "reason": ""},
            ctx,
        )
        assert result["valid"] is True

    def test_set_priority_invalid(self):
        ctx = _make_context()
        result = _enrich_action(
            {"action": "set_task_priority", "target": {"pid": 1234, "priority": "extreme"}, "reason": ""},
            ctx,
        )
        assert result["valid"] is False

    def test_configure_budget_valid(self):
        ctx = _make_context()
        result = _enrich_action(
            {"action": "configure_budget", "target": {"enabled": True, "total_power_budget": 1200}, "reason": ""},
            ctx,
        )
        assert result["valid"] is True

    def test_configure_budget_out_of_range(self):
        ctx = _make_context()
        result = _enrich_action(
            {"action": "configure_budget", "target": {"enabled": True, "total_power_budget": 100}, "reason": ""},
            ctx,
        )
        assert result["valid"] is False

    def test_run_schedule_once(self):
        ctx = _make_context()
        result = _enrich_action(
            {"action": "run_schedule_once", "target": {}, "reason": ""},
            ctx,
        )
        assert result["valid"] is True


# ─── 启发式计划生成 ────────────────────────────────────────

class TestBuildHeuristicPlan:
    def test_schedule_once(self):
        plan = _build_heuristic_plan("执行调度一次")
        assert len(plan["actions"]) >= 1
        assert plan["actions"][0]["action"] == "run_schedule_once"
        assert plan["planner"] == "rule"

    def test_budget_setting(self):
        plan = _build_heuristic_plan("把总功率预算设为1200W")
        assert any(a["action"] == "configure_budget" for a in plan["actions"])
        budget_action = [a for a in plan["actions"] if a["action"] == "configure_budget"][0]
        assert budget_action["target"]["total_power_budget"] == 1200

    def test_power_limit(self):
        plan = _build_heuristic_plan("把GPU 0功耗上限设到250W")
        assert any(a["action"] == "set_power_limit" for a in plan["actions"])

    def test_pause_task(self):
        plan = _build_heuristic_plan("暂停进程 12345")
        assert any(a["action"] == "pause_task" for a in plan["actions"])
        assert plan["actions"][0]["target"]["pid"] == 12345

    def test_terminate_task(self):
        plan = _build_heuristic_plan("终止 PID 6789")
        assert any(a["action"] == "terminate_task" for a in plan["actions"])
        assert plan["requires_confirmation"] is True

    def test_no_action(self):
        plan = _build_heuristic_plan("今天天气怎么样")
        assert len(plan["actions"]) == 0
        assert len(plan["warnings"]) > 0

    def test_resume_task(self):
        plan = _build_heuristic_plan("恢复进程 1111")
        assert any(a["action"] == "resume_task" for a in plan["actions"])

    def test_priority_setting(self):
        plan = _build_heuristic_plan("把进程 2222 设为紧急")
        assert any(a["action"] == "set_task_priority" for a in plan["actions"])
