import importlib
import os
import sys
import types
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "server-agent"))
sys.modules.setdefault("pynvml", types.SimpleNamespace())

agent_main = importlib.import_module("main")


class AgentStartupLoggingTests(unittest.TestCase):
    def test_build_agent_startup_message_explains_missing_local_nvml(self):
        fake_monitor = types.SimpleNamespace(
            device_count=0,
            startup_issue="NVML 初始化失败，当前无法采集真实 GPU 数据: NVML Shared Library Not Found",
        )
        original = agent_main.gpu_monitor
        agent_main.gpu_monitor = fake_monitor
        try:
            level, message = agent_main.build_agent_startup_message()
        finally:
            agent_main.gpu_monitor = original

        self.assertEqual(level, agent_main.logging.WARNING)
        self.assertIn("NVML Shared Library Not Found", message)
        self.assertIn("SSH Linux / 远程 Agent", message)

    def test_build_agent_startup_message_reports_detected_gpu_count(self):
        fake_monitor = types.SimpleNamespace(device_count=3, startup_issue="")
        original = agent_main.gpu_monitor
        agent_main.gpu_monitor = fake_monitor
        try:
            level, message = agent_main.build_agent_startup_message()
        finally:
            agent_main.gpu_monitor = original

        self.assertEqual(level, agent_main.logging.INFO)
        self.assertIn("3 张GPU", message)


if __name__ == "__main__":
    unittest.main()
