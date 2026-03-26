import os
import sys
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.privacy import PrivacyService  # noqa: E402
from app.services.scheduler import SchedulerEngine  # noqa: E402


class FakeAgent:
    def __init__(self):
        self.calls = []

    async def set_power_limit(self, gpu_index, power_limit):
        self.calls.append(("set_power_limit", gpu_index, power_limit))
        return {"success": True}

    async def pause_task(self, pid):
        self.calls.append(("pause_task", pid))
        return {"success": True}

    async def resume_task(self, pid):
        self.calls.append(("resume_task", pid))
        return {"success": True}


class FakeStore:
    def __init__(self):
        self.logs = []

    async def save_schedule_log(self, action, target, reason, result=""):
        self.logs.append((action, target, reason, result))

    async def get_all_task_priorities(self):
        return {}


class FakeLLM:
    def __init__(self):
        self.task_data = None

    async def generate_schedule(self, gpu_data, task_data, time_period):
        self.task_data = task_data
        return {"actions": [], "summary": "ok", "estimated_power_saving": 0}


class SchedulerEngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_execute_actions_dry_run_does_not_call_agent(self):
        agent = FakeAgent()
        store = FakeStore()
        scheduler = SchedulerEngine(agent, store)

        results = await scheduler.execute_actions(
            [
                {
                    "action": "set_power_limit",
                    "target": {"gpu_index": 0, "power_limit": 200},
                    "reason": "test",
                }
            ],
            dry_run=True,
        )

        self.assertTrue(results[0]["success"])
        self.assertTrue(results[0]["dry_run"])
        self.assertEqual(agent.calls, [])
        self.assertEqual(store.logs, [])

    async def test_execute_actions_real_calls_agent_and_logs(self):
        agent = FakeAgent()
        store = FakeStore()
        scheduler = SchedulerEngine(agent, store)

        results = await scheduler.execute_actions(
            [
                {
                    "action": "pause_task",
                    "target": {"pid": 123},
                    "reason": "test",
                }
            ],
        )

        self.assertTrue(results[0]["success"])
        self.assertEqual(agent.calls, [("pause_task", 123)])
        self.assertEqual(len(store.logs), 1)

    async def test_run_ai_schedule_uses_sanitized_processes(self):
        agent = FakeAgent()
        store = FakeStore()
        llm = FakeLLM()
        privacy = PrivacyService()
        scheduler = SchedulerEngine(agent, store, llm_service=llm, privacy_service=privacy)

        await scheduler.run_ai_schedule(
            [{"index": 0, "power_usage": 120, "power_limit": 140}],
            [
                {
                    "pid": 321,
                    "username": "alice",
                    "command": r"C:\Users\alice\project\train.py",
                    "priority": "normal",
                }
            ],
        )

        self.assertIsNotNone(llm.task_data)
        self.assertNotEqual(llm.task_data[0]["username"], "alice")
        self.assertIn("[path]", llm.task_data[0]["command"])


if __name__ == "__main__":
    unittest.main()
