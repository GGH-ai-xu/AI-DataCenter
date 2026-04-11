import os
import sys
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.goal_runtime.session_context import (  # noqa: E402
    SessionContextBudgetError,
    build_session_context_payload,
    format_session_context_for_prompt,
)


SESSION = {
    "session_id": "sess-memory",
    "status": "completed",
    "live_phase": "completed",
    "summary": "继续刚才那个任务",
    "goal_json": {
        "message": "第一轮问题",
        "raw_message": "第一轮问题",
        "last_message": "继续刚才那个任务",
    },
}

EVENTS = [
    {
        "event_type": "UserMessageSubmitted",
        "payload": {"content": "第一轮问题"},
        "round_index": 1,
        "sequence": 0,
        "source": "chat",
    },
    {
        "event_type": "AssistantMessageGenerated",
        "payload": {"content": "第一轮回答"},
        "round_index": 1,
        "sequence": 1,
        "source": "chat",
    },
    {
        "event_type": "PlanCreated",
        "payload": {"summary": "准备将 GPU 3 功耗上限设置为 220W"},
        "round_index": 2,
        "sequence": 2,
        "source": "planner",
    },
    {
        "event_type": "AwaitingApproval",
        "payload": {"summary": "等待审批"},
        "round_index": 2,
        "sequence": 3,
        "source": "runtime",
    },
    {
        "event_type": "SessionCompleted",
        "payload": {"summary": "set_power_limit GPU 3 -> 220W succeeded"},
        "round_index": 2,
        "sequence": 4,
        "source": "runtime",
    },
    {
        "event_type": "UserMessageSubmitted",
        "payload": {"content": "继续刚才那个任务"},
        "round_index": 3,
        "sequence": 0,
        "source": "chat",
    },
]


class SessionContextBuilderTests(unittest.TestCase):
    def test_build_payload_keeps_recent_rounds_and_summarizes_older_ones(self):
        payload = build_session_context_payload(
            SESSION,
            EVENTS,
            "继续刚才那个任务",
            recent_round_limit=1,
            max_prompt_chars=1200,
        )

        self.assertEqual(payload["session_id"], "sess-memory")
        self.assertEqual(payload["current_request"]["message"], "继续刚才那个任务")
        self.assertEqual(len(payload["recent_messages"]), 1)
        self.assertEqual(payload["recent_messages"][0]["round_index"], 3)
        self.assertEqual(payload["historical_summary"]["round_count"], 2)
        self.assertIn("第一轮问题", "\n".join(payload["historical_summary"]["summary_lines"]))
        self.assertEqual(payload["runtime_summary"]["latest_plan"], "准备将 GPU 3 功耗上限设置为 220W")
        self.assertEqual(
            payload["runtime_summary"]["latest_execution"],
            "set_power_limit GPU 3 -> 220W succeeded",
        )

    def test_prompt_format_includes_summary_recent_rounds_and_runtime_summary(self):
        payload = build_session_context_payload(
            SESSION,
            EVENTS,
            "继续刚才那个任务",
            recent_round_limit=1,
            max_prompt_chars=1200,
        )

        prompt = format_session_context_for_prompt(payload)
        self.assertIn("会话历史摘要：", prompt)
        self.assertIn("最近对话原文：", prompt)
        self.assertIn("运行态摘要：", prompt)
        self.assertIn("第一轮问题", prompt)
        self.assertIn("set_power_limit GPU 3 -> 220W succeeded", prompt)

    def test_builder_raises_when_budget_is_still_exceeded_after_summary_compression(self):
        with self.assertRaises(SessionContextBudgetError):
            build_session_context_payload(
                SESSION,
                EVENTS * 12,
                "继续刚才那个任务",
                recent_round_limit=2,
                max_prompt_chars=80,
            )


if __name__ == "__main__":
    unittest.main()
