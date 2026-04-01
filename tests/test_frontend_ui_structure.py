import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendUIStructureTests(unittest.TestCase):
    def test_workspace_shell_components_exist(self):
        for rel in [
            "frontend/src/components/workspace/WorkspaceTabs.vue",
            "frontend/src/components/workspace/WorkspaceSummary.vue",
            "frontend/src/components/workspace/WorkspacePaneLayout.vue",
        ]:
            self.assertTrue((ROOT / rel).exists(), rel)

    def test_major_views_use_tab_state(self):
        for rel in [
            "frontend/src/views/Dashboard.vue",
            "frontend/src/views/TaskManager.vue",
            "frontend/src/views/Scheduler.vue",
            "frontend/src/views/EnergyOptimization.vue",
            "frontend/src/views/AIAssistant.vue",
        ]:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("activeTab", text, rel)
            self.assertIn("WorkspaceTabs", text, rel)

    def test_monitor_and_alert_views_use_shared_shell(self):
        for rel in [
            "frontend/src/views/MonitorCenter.vue",
            "frontend/src/views/AlertCenter.vue",
        ]:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("WorkspaceSummary", text, rel)

    def test_vite_build_still_available(self):
        package_json = (ROOT / "frontend/package.json").read_text(encoding="utf-8")
        self.assertIn('"build": "vite build"', package_json)


if __name__ == "__main__":
    unittest.main()
