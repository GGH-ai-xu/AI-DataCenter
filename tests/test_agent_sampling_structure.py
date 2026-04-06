import os
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.path.join(ROOT, "server-agent"))

from collectors import system_monitor, task_monitor  # noqa: E402


class AgentSamplingTests(unittest.TestCase):
    def test_get_system_info_uses_non_blocking_cpu_sampling(self):
        cpu_calls = []

        def fake_cpu_percent(interval=None, percpu=False):
            cpu_calls.append((interval, percpu))
            if percpu:
                return [10.0, 20.0]
            return 15.0

        fake_memory = mock.Mock(total=1, used=1, percent=50, available=1)
        fake_swap = mock.Mock(total=1, used=0, percent=0)

        with mock.patch.object(system_monitor.psutil, "cpu_percent", side_effect=fake_cpu_percent):
            with mock.patch.object(system_monitor.psutil, "virtual_memory", return_value=fake_memory):
                with mock.patch.object(system_monitor.psutil, "swap_memory", return_value=fake_swap):
                    with mock.patch.object(system_monitor.psutil, "cpu_count", return_value=8):
                        system_monitor.get_system_info()

        self.assertTrue(cpu_calls)
        self.assertTrue(all(call[0] in (None, 0) for call in cpu_calls))

    def test_cached_gpu_processes_reuses_recent_snapshot(self):
        get_cached_gpu_processes = getattr(task_monitor, "get_cached_gpu_processes")

        fake_processes = [{"pid": 1, "gpu_index": 0}]
        with mock.patch.object(task_monitor, "get_all_gpu_processes", return_value=fake_processes) as mocked_scan:
            with mock.patch.object(task_monitor.time, "time", side_effect=[100.0, 101.0, 103.5]):
                first = get_cached_gpu_processes(1)
                second = get_cached_gpu_processes(1)
                third = get_cached_gpu_processes(1)

        self.assertEqual(mocked_scan.call_count, 2)
        self.assertEqual(first, second)
        self.assertEqual(third, fake_processes)
        self.assertIsNot(first, second)

    def test_agent_main_uses_cached_process_snapshots(self):
        text = (ROOT / "server-agent/main.py").read_text(encoding="utf-8")

        self.assertIn("get_cached_gpu_processes", text)
        self.assertNotIn("get_all_gpu_processes(gpu_monitor.device_count", text)


if __name__ == "__main__":
    unittest.main()
