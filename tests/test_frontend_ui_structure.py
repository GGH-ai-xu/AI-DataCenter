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

    def test_dashboard_is_summary_only(self):
        text = (ROOT / "frontend/src/views/Dashboard.vue").read_text(encoding="utf-8")

        self.assertNotIn("执行一次真实治理", text)
        self.assertNotIn("先做节能测算", text)
        self.assertNotIn("一键导出综合报告", text)
        self.assertNotIn("executeDispatch", text)
        self.assertNotIn("measureOptimization", text)

    def test_scheduler_no_longer_hosts_energy_report(self):
        text = (ROOT / "frontend/src/views/Scheduler.vue").read_text(encoding="utf-8")

        self.assertNotIn("AI 能耗分析报告", text)
        self.assertNotIn("getScheduleReport", text)

    def test_monitor_center_no_longer_hosts_replay_tab(self):
        text = (ROOT / "frontend/src/views/MonitorCenter.vue").read_text(encoding="utf-8")

        self.assertNotIn("{ key: 'replay'", text)
        self.assertNotIn("activeTab === 'replay'", text)

    def test_ai_assistant_no_longer_allows_real_execution(self):
        text = (ROOT / "frontend/src/views/AIAssistant.vue").read_text(encoding="utf-8")

        self.assertNotIn("执行真实动作", text)
        self.assertNotIn("controlMode === 'real'", text)
        self.assertNotIn("将执行真实治理动作", text)


if __name__ == "__main__":
    unittest.main()
