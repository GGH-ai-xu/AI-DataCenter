import sys
import types
import unittest
from unittest import mock

from app.api import agent_runtime as agent_runtime_api


class _FakeGoalRuntime:
    def __init__(self):
        self.list_calls = []
        self.delete_calls = []

    async def list_sessions(self, limit=20):
        self.list_calls.append(limit)
        return [
            {
                "session_id": "session-1",
                "status": "completed",
                "summary": "列出最近会话",
                "goal_json": {"message": "列出最近会话"},
                "updated_at": 1710000000,
            },
        ]

    async def delete_session(self, session_id):
        self.delete_calls.append(session_id)
        return {"session_id": session_id, "deleted": True}


class AgentRuntimeRouteTests(unittest.IsolatedAsyncioTestCase):
    def test_agent_runtime_api_exposes_history_and_delete_handlers(self):
        self.assertTrue(hasattr(agent_runtime_api, "list_agent_runtime_sessions"))
        self.assertTrue(hasattr(agent_runtime_api, "delete_agent_runtime_session"))

    async def test_list_agent_runtime_sessions_reads_goal_runtime_history(self):
        fake_goal_runtime = _FakeGoalRuntime()
        fake_main = types.SimpleNamespace(
            app_state=types.SimpleNamespace(goal_runtime=fake_goal_runtime)
        )

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            result = await agent_runtime_api.list_agent_runtime_sessions(limit=5)

        self.assertEqual(fake_goal_runtime.list_calls, [5])
        self.assertEqual(result["sessions"][0]["session_id"], "session-1")

    async def test_delete_agent_runtime_session_calls_goal_runtime(self):
        fake_goal_runtime = _FakeGoalRuntime()
        fake_main = types.SimpleNamespace(
            app_state=types.SimpleNamespace(goal_runtime=fake_goal_runtime)
        )

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            result = await agent_runtime_api.delete_agent_runtime_session("session-1")

        self.assertEqual(fake_goal_runtime.delete_calls, ["session-1"])
        self.assertTrue(result["deleted"])


if __name__ == "__main__":
    unittest.main()
