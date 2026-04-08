import os
import sys
import tempfile
import unittest
from unittest import mock


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.import_context import ImportContextService  # noqa: E402


class ImportContextServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.tempdir.name, "import-context.json")
        self.service = ImportContextService(
            self.config_path,
            "http://127.0.0.1:8001",
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_save_import_persists_selected_gpu_indexes_and_snapshot(self):
        self.service.load()

        saved = self.service.save_import(
            source_mode="remote",
            agent_url="http://10.0.0.8:8001",
            agent_label="实验室 A",
            gpu_indexes=[0, 2],
            system_info={
                "cpu_percent": 12.5,
                "cpu_count": 32,
                "memory_total": 256000,
            },
            gpus=[
                {
                    "index": 0,
                    "name": "RTX 4090",
                    "temperature": 62,
                    "power_usage": 280,
                    "memory_used": 4096,
                    "memory_total": 24564,
                    "gpu_utilization": 88,
                    "timestamp": 1.0,
                },
                {
                    "index": 2,
                    "name": "RTX 6000",
                    "temperature": 55,
                    "power_usage": 210,
                    "memory_used": 2048,
                    "memory_total": 49140,
                    "gpu_utilization": 64,
                    "timestamp": 1.0,
                },
            ],
        )

        self.assertEqual(saved["source_mode"], "remote")
        self.assertEqual(saved["agent_label"], "实验室 A")
        self.assertEqual(saved["imported_gpu_indexes"], [0, 2])
        self.assertTrue(saved["valid"])

        reloaded = ImportContextService(
            self.config_path,
            "http://127.0.0.1:8001",
        ).load()
        self.assertEqual(reloaded["imported_gpu_indexes"], [0, 2])
        self.assertEqual(reloaded["snapshot"]["gpus"][1]["index"], 2)

    def test_filter_helpers_only_keep_imported_scope(self):
        self.service.load()
        self.service.save_import(
            source_mode="local",
            agent_url="http://127.0.0.1:8001",
            agent_label="本机 Agent",
            gpu_indexes=[1],
            system_info={
                "cpu_percent": 18.0,
                "cpu_count": 16,
                "memory_total": 128000,
            },
            gpus=[
                {
                    "index": 1,
                    "name": "RTX 4080",
                    "temperature": 58,
                    "power_usage": 240,
                    "memory_used": 2048,
                    "memory_total": 16384,
                    "gpu_utilization": 72,
                    "timestamp": 1.0,
                },
            ],
        )

        filtered_gpus = self.service.filter_gpus(
            [
                {"index": 0, "name": "GPU0"},
                {"index": 1, "name": "GPU1"},
                {"index": 2, "name": "GPU2"},
            ]
        )
        filtered_processes = self.service.filter_processes(
            [
                {"pid": 11, "gpu_index": 1, "command": "train.py"},
                {"pid": 22, "gpu_index": 0, "command": "other.py"},
            ]
        )

        self.assertEqual([gpu["index"] for gpu in filtered_gpus], [1])
        self.assertEqual([proc["pid"] for proc in filtered_processes], [11])

    def test_validate_runtime_marks_context_invalid_when_selected_gpu_disappears(self):
        self.service.load()
        self.service.save_import(
            source_mode="remote",
            agent_url="http://10.0.0.8:8001",
            agent_label="实验室 A",
            gpu_indexes=[0, 1],
            system_info={
                "cpu_percent": 22.0,
                "cpu_count": 32,
                "memory_total": 256000,
            },
            gpus=[
                {
                    "index": 0,
                    "name": "RTX 4090",
                    "temperature": 62,
                    "power_usage": 280,
                    "memory_used": 4096,
                    "memory_total": 24564,
                    "gpu_utilization": 88,
                    "timestamp": 1.0,
                },
                {
                    "index": 1,
                    "name": "RTX 4090",
                    "temperature": 60,
                    "power_usage": 260,
                    "memory_used": 4096,
                    "memory_total": 24564,
                    "gpu_utilization": 81,
                    "timestamp": 1.0,
                },
            ],
        )

        snapshot = self.service.validate_runtime(
            {"status": "ok"},
            [{"index": 0, "name": "RTX 4090"}],
        )

        self.assertFalse(snapshot["valid"])
        self.assertIn("GPU 1", snapshot["invalid_reason"])

    def test_validate_runtime_keeps_import_snapshot_without_rewriting_file(self):
        self.service.load()
        self.service.save_import(
            source_mode="local",
            agent_url="http://127.0.0.1:8001",
            agent_label="本机 Agent",
            gpu_indexes=[1],
            system_info={
                "cpu_percent": 18.0,
                "cpu_count": 16,
                "memory_total": 128000,
            },
            gpus=[
                {
                    "index": 1,
                    "name": "RTX 4080",
                    "temperature": 58,
                    "power_usage": 240,
                    "memory_used": 2048,
                    "memory_total": 16384,
                    "gpu_utilization": 72,
                    "timestamp": 1.0,
                },
            ],
        )

        with mock.patch.object(self.service, "_persist") as persist_mock:
            snapshot = self.service.validate_runtime(
                {"status": "ok"},
                [
                    {
                        "index": 1,
                        "name": "RTX 4080",
                        "temperature": 77,
                    }
                ],
            )

        self.assertTrue(snapshot["valid"])
        self.assertEqual(snapshot["snapshot"]["gpus"][0]["temperature"], 58)
        persist_mock.assert_not_called()

    def test_validate_runtime_without_import_does_not_persist_same_empty_state(self):
        self.service.load()

        with mock.patch.object(self.service, "_persist") as persist_mock:
            snapshot = self.service.validate_runtime(None, [])

        self.assertFalse(snapshot["valid"])
        self.assertEqual(snapshot["invalid_reason"], "尚未导入任何 GPU")
        persist_mock.assert_not_called()

    def test_validate_runtime_same_invalid_reason_does_not_repeat_persist(self):
        self.service.load()
        self.service.save_import(
            source_mode="remote",
            agent_url="http://10.0.0.8:8001",
            agent_label="实验室 A",
            gpu_indexes=[0],
            system_info={"cpu_percent": 22.0, "cpu_count": 32, "memory_total": 256000},
            gpus=[
                {
                    "index": 0,
                    "name": "RTX 4090",
                    "temperature": 62,
                    "power_usage": 280,
                    "memory_used": 4096,
                    "memory_total": 24564,
                    "gpu_utilization": 88,
                    "timestamp": 1.0,
                }
            ],
        )
        self.service.validate_runtime(None, [])

        with mock.patch.object(self.service, "_persist") as persist_mock:
            snapshot = self.service.validate_runtime(None, [])

        self.assertFalse(snapshot["valid"])
        self.assertEqual(snapshot["invalid_reason"], "当前导入目标不可达，需要重新导入")
        persist_mock.assert_not_called()

    def test_validate_runtime_marks_selected_unavailable_gpu_invalid(self):
        self.service.load()
        self.service.save_import(
            source_mode="remote",
            agent_url="http://10.0.0.8:8001",
            agent_label="实验室 A",
            gpu_indexes=[1],
            system_info={"cpu_percent": 22.0, "cpu_count": 32, "memory_total": 256000},
            gpus=[
                {
                    "index": 1,
                    "name": "RTX 4090",
                    "temperature": 60,
                    "power_usage": 260,
                    "memory_used": 4096,
                    "memory_total": 24564,
                    "gpu_utilization": 81,
                    "timestamp": 1.0,
                },
            ],
        )

        snapshot = self.service.validate_runtime(
            {"status": "ok"},
            [
                {
                    "index": 1,
                    "name": "RTX 4090",
                    "available": False,
                    "error": "Unknown Error",
                },
            ],
        )

        self.assertFalse(snapshot["valid"])
        self.assertEqual(snapshot["invalid_reason"], "已导入的 GPU 1 当前不可用")


if __name__ == "__main__":
    unittest.main()
