import inspect
import os
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.path.join(ROOT, "server-agent"))

from collectors import gpu_monitor as gpu_monitor_module  # noqa: E402
from collectors import task_monitor as task_monitor_module  # noqa: E402
from controllers import power_control as power_control_module  # noqa: E402
from controllers import task_control as task_control_module  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "backend"))
from app.models import schemas as schema_module  # noqa: E402
from app.services.scheduler import SchedulerEngine  # noqa: E402


class RealDataOnlyStructureTests(unittest.TestCase):
    def test_gpu_monitor_without_nvml_returns_no_fake_gpus(self):
        monitor = gpu_monitor_module.GPUMonitor()

        with mock.patch.object(gpu_monitor_module, "NVML_AVAILABLE", False):
            monitor.init()

        self.assertEqual(monitor.device_count, 0)
        self.assertEqual(monitor.get_all_gpus(), [])
        self.assertIsNone(monitor.get_gpu_info(0))
        self.assertFalse(hasattr(monitor, "is_simulated"))

    def test_server_agent_runtime_no_longer_accepts_simulate_parameters(self):
        self.assertNotIn(
            "simulate",
            inspect.signature(task_monitor_module.get_all_gpu_processes).parameters,
        )
        self.assertNotIn(
            "simulate",
            inspect.signature(task_monitor_module.get_cached_gpu_processes).parameters,
        )
        self.assertNotIn(
            "simulate",
            inspect.signature(power_control_module.set_power_limit).parameters,
        )
        self.assertNotIn(
            "simulate",
            inspect.signature(task_control_module.pause_task).parameters,
        )
        self.assertNotIn(
            "simulate",
            inspect.signature(task_control_module.resume_task).parameters,
        )
        self.assertNotIn(
            "simulate",
            inspect.signature(task_control_module.terminate_task).parameters,
        )

    def test_system_and_dashboard_remove_demo_alert_workflow(self):
        system_text = (ROOT / "backend/app/api/system.py").read_text(encoding="utf-8")
        api_text = (ROOT / "frontend/src/services/api.js").read_text(encoding="utf-8")
        dashboard_text = (ROOT / "frontend/src/views/Dashboard.vue").read_text(encoding="utf-8")

        self.assertNotIn('"/demo-alert"', system_text)
        self.assertNotIn("create_demo_alert", system_text)
        self.assertNotIn("测试告警", system_text)
        self.assertNotIn("createDemoAlert", api_text)
        self.assertNotIn("demoAlert", dashboard_text)
        self.assertNotIn("生成测试告警", dashboard_text)

    def test_frontend_real_data_labels_remove_simulated_collection_states(self):
        store_text = (ROOT / "frontend/src/stores/app.js").read_text(encoding="utf-8")
        energy_text = (ROOT / "frontend/src/views/EnergyOptimization.vue").read_text(encoding="utf-8")

        self.assertNotIn("模拟演示", store_text)
        self.assertNotIn("simulated", store_text)
        self.assertNotIn("模拟采集", energy_text)
        self.assertNotIn("当前为演示模式", energy_text)

    def test_runtime_execution_no_longer_uses_dry_run(self):
        tasks_api_text = (ROOT / "backend/app/api/tasks.py").read_text(encoding="utf-8")
        scheduler_api_text = (ROOT / "backend/app/api/scheduler.py").read_text(encoding="utf-8")
        ai_api_text = (ROOT / "backend/app/api/ai.py").read_text(encoding="utf-8")
        ai_service_text = (ROOT / "backend/app/services/ai_control.py").read_text(encoding="utf-8")

        self.assertNotIn("dry_run", inspect.signature(schema_module.TaskActionRequest).parameters)
        self.assertNotIn("dry_run", inspect.signature(schema_module.PowerLimitRequest).parameters)
        self.assertNotIn("dry_run", inspect.signature(schema_module.ScheduleRunRequest).parameters)
        self.assertNotIn("dry_run", inspect.signature(schema_module.AIControlExecuteRequest).parameters)
        self.assertNotIn("dry_run", inspect.signature(SchedulerEngine.execute_actions).parameters)
        self.assertNotIn("dry_run", tasks_api_text)
        self.assertNotIn("dry_run", scheduler_api_text)
        self.assertNotIn("dry_run", ai_api_text)
        self.assertNotIn("dry_run", ai_service_text)

    def test_frontend_execution_pages_remove_rehearsal_mode(self):
        task_text = (ROOT / "frontend/src/views/TaskManager.vue").read_text(encoding="utf-8")
        scheduler_text = (ROOT / "frontend/src/views/Scheduler.vue").read_text(encoding="utf-8")
        ai_text = (ROOT / "frontend/src/views/AIAssistant.vue").read_text(encoding="utf-8")

        self.assertNotIn("演练模式", task_text)
        self.assertNotIn("dry_run", task_text)
        self.assertNotIn("演练模式", scheduler_text)
        self.assertNotIn("dry_run", scheduler_text)
        self.assertNotIn("执行演练", ai_text)
        self.assertNotIn("演练", ai_text)
        self.assertNotIn("dry_run", ai_text)

    def test_readme_and_scripts_remove_demo_naming(self):
        readme_text = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertNotIn("launch-demo", readme_text)
        self.assertNotIn("演练模式", readme_text)
        self.assertFalse((ROOT / "scripts/launch-demo.ps1").exists())


if __name__ == "__main__":
    unittest.main()
