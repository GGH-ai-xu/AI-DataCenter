import os
import sys
import tempfile
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.data_store import DataStore  # noqa: E402


class GoalRuntimeDataStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_data_store_persists_runtime_session_and_events(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = DataStore(os.path.join(tmpdir, "runtime.db"))
            await store.init()
            try:
                await store.create_agent_session(
                    session_id="sess-1",
                    goal_json={"message": "分析当前集群"},
                    permission_mode="low",
                    status="running",
                    summary="分析当前集群",
                )
                await store.append_agent_event(
                    session_id="sess-1",
                    event_type="GoalParsed",
                    payload={"summary": "分析当前集群"},
                )
                await store.update_agent_session_status(
                    session_id="sess-1",
                    status="completed",
                    summary="分析已完成",
                )

                session = await store.get_agent_session("sess-1")
                events = await store.get_agent_events("sess-1")
            finally:
                await store.close()

        self.assertEqual(session["status"], "completed")
        self.assertEqual(session["summary"], "分析已完成")
        self.assertEqual(session["goal_json"]["message"], "分析当前集群")
        self.assertEqual(events[0]["event_type"], "GoalParsed")
        self.assertEqual(events[0]["payload"]["summary"], "分析当前集群")

    async def test_append_agent_event_persists_round_sequence_source_and_duration(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = DataStore(os.path.join(tmpdir, "runtime.db"))
            await store.init()
            try:
                await store.create_agent_session(
                    "sess-1",
                    {"message": "把 GPU 0 的功耗上限调到 220W"},
                    "low",
                    "running",
                    "把 GPU 0 的功耗上限调到 220W",
                )
                await store.append_agent_event(
                    "sess-1",
                    "LLMRequestPrepared",
                    {"summary": "准备调用 LLM", "prompt_preview": "用户指令..."},
                    round_index=1,
                    sequence=2,
                    source="llm",
                    duration_ms=35,
                )

                events = await store.get_agent_events("sess-1")
            finally:
                await store.close()

        self.assertEqual(events[0]["round_index"], 1)
        self.assertEqual(events[0]["sequence"], 2)
        self.assertEqual(events[0]["source"], "llm")
        self.assertEqual(events[0]["duration_ms"], 35)
        self.assertEqual(events[0]["payload"]["prompt_preview"], "用户指令...")

    async def test_data_store_overwrites_latest_planner_stream_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = DataStore(os.path.join(tmpdir, "runtime.db"))
            await store.init()
            try:
                await store.create_agent_session(
                    session_id="sess-2",
                    goal_json={"message": "执行一次调度"},
                    permission_mode="low",
                    status="running",
                    summary="执行一次调度",
                )
                await store.update_agent_session_status(
                    "sess-2",
                    "running",
                    "执行一次调度",
                    live_phase="planning",
                )
                await store.upsert_agent_stream_state(
                    "sess-2",
                    "planner",
                    latest_text="第一版计划",
                    latest_char_count=5,
                    revision=1,
                )
                await store.upsert_agent_stream_state(
                    "sess-2",
                    "planner",
                    latest_text="第二版计划",
                    latest_char_count=6,
                    revision=2,
                )

                session = await store.get_agent_session("sess-2")
                stream_state = await store.get_agent_stream_state(
                    "sess-2",
                    "planner",
                )
            finally:
                await store.close()

        self.assertEqual(session["live_phase"], "planning")
        self.assertEqual(stream_state["latest_text"], "第二版计划")
        self.assertEqual(stream_state["revision"], 2)


if __name__ == "__main__":
    unittest.main()
