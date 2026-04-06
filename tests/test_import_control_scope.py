import os
import sys
import types
import unittest
from unittest import mock


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.api.gpu import get_realtime  # noqa: E402
from app.api.tasks import get_tasks, pause_task  # noqa: E402
from app.models.schemas import TaskActionRequest  # noqa: E402


class FakeAgent:
    async def get_all_gpus(self):
        return [{"index": 0, "name": "GPU0"}, {"index": 1, "name": "GPU1"}]

    async def get_system_info(self):
        return {"cpu_percent": 10}

    async def get_processes(self):
        return [
            {"pid": 10, "gpu_index": 0, "command": "python a.py", "priority": "normal"},
            {"pid": 11, "gpu_index": 1, "command": "python b.py", "priority": "normal"},
        ]

    async def pause_task(self, pid):
        return {"success": True, "pid": pid}

    async def resume_task(self, pid):
        return {"success": True, "pid": pid}

    async def terminate_task(self, pid):
        return {"success": True, "pid": pid}


class FakeStore:
    async def get_all_task_priorities(self):
        return {10: "normal", 11: "urgent"}

    async def save_audit_log(self, **kwargs):
        return None


class FakePrivacy:
    def sanitize_processes(self, processes):
        return processes


class FakeImportContext:
    def filter_gpus(self, gpus):
        return [gpu for gpu in gpus if gpu["index"] == 1]

    def filter_processes(self, processes):
        return [proc for proc in processes if proc["gpu_index"] == 1]

    def ensure_process_allowed(self, pid, processes):
        allowed = {proc["pid"] for proc in self.filter_processes(processes)}
        if pid not in allowed:
            raise ValueError(f"PID {pid} 不在当前导入范围内")


class ImportControlScopeTests(unittest.IsolatedAsyncioTestCase):
    async def test_gpu_realtime_only_returns_imported_gpus(self):
        fake_main = types.SimpleNamespace(
            app_state=types.SimpleNamespace(
                agent=FakeAgent(),
                import_context=FakeImportContext(),
            )
        )

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            payload = await get_realtime()

        self.assertEqual([item["index"] for item in payload["gpus"]], [1])
        self.assertEqual(payload["system"]["cpu_percent"], 10)

    async def test_tasks_list_only_returns_imported_gpu_processes(self):
        fake_main = types.SimpleNamespace(
            app_state=types.SimpleNamespace(
                agent=FakeAgent(),
                store=FakeStore(),
                privacy=FakePrivacy(),
                import_context=FakeImportContext(),
            )
        )

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            payload = await get_tasks()

        self.assertEqual([item["pid"] for item in payload["processes"]], [11])
        self.assertEqual(payload["processes"][0]["priority"], "urgent")

    async def test_pause_task_rejects_pid_outside_import_scope(self):
        fake_main = types.SimpleNamespace(
            app_state=types.SimpleNamespace(
                agent=FakeAgent(),
                store=FakeStore(),
                privacy=FakePrivacy(),
                import_context=FakeImportContext(),
            )
        )

        with mock.patch.dict(sys.modules, {"app.main": fake_main}):
            with self.assertRaisesRegex(Exception, "当前导入范围内"):
                await pause_task(TaskActionRequest(pid=10, acknowledge_risk=True))


if __name__ == "__main__":
    unittest.main()
