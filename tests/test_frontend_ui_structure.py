import unittest
import re
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

    def test_workspace_tabs_support_vertical_orientation(self):
        text = (ROOT / "frontend/src/components/workspace/WorkspaceTabs.vue").read_text(encoding="utf-8")

        self.assertIn("orientation", text)
        self.assertIn("workspace-tabs--vertical", text)

    def test_workbench_pages_use_left_nav_layout(self):
        for rel in [
            "frontend/src/views/Dashboard.vue",
            "frontend/src/views/Scheduler.vue",
            "frontend/src/views/MonitorCenter.vue",
            "frontend/src/views/TaskManager.vue",
            "frontend/src/views/EnergyOptimization.vue",
            "frontend/src/views/AIAssistant.vue",
        ]:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("workspace-nav-layout", text, rel)
            self.assertIn("workspace-nav-layout__nav", text, rel)
            self.assertIn("workspace-nav-layout__content", text, rel)
            self.assertIn('orientation="vertical"', text, rel)

    def test_shared_style_defines_sticky_workbench_nav(self):
        text = (ROOT / "frontend/src/style.css").read_text(encoding="utf-8")

        self.assertIn(".workspace-nav-layout", text)
        self.assertIn(".workspace-nav-layout__nav", text)
        self.assertIn("position: sticky", text)
        self.assertIn(".workspace-tabs--vertical", text)

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

    def test_frontend_brand_uses_repo_logo_asset(self):
        app_text = (ROOT / "frontend/src/App.vue").read_text(encoding="utf-8")
        favicon_text = (ROOT / "frontend/public/favicon.svg").read_text(encoding="utf-8")
        source_logo = (ROOT / "docs/logo/logo.svg").read_text(encoding="utf-8")

        self.assertIn('src="/logo.svg"', app_text)
        self.assertEqual(favicon_text.strip(), source_logo.strip())

    def test_desktop_shell_uses_updated_logo_assets(self):
        splash_text = (ROOT / "desktop-shell/splash.html").read_text(encoding="utf-8")
        package_text = (ROOT / "desktop-shell/package.json").read_text(encoding="utf-8")
        main_text = (ROOT / "desktop-shell/main.js").read_text(encoding="utf-8")
        icon_bytes = (ROOT / "desktop-shell/build/icon.ico").read_bytes()

        self.assertIn("brand-logo", splash_text)
        self.assertIn('"build/icon.png"', package_text)
        self.assertIn('"build/icon.ico"', package_text)
        self.assertIn("process.platform === 'win32'", main_text)
        self.assertIn("icon.ico", main_text)
        self.assertIn("icon.png", main_text)
        self.assertGreater(int.from_bytes(icon_bytes[4:6], "little"), 1)

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

    def test_monitor_center_cards_define_own_padding(self):
        text = (ROOT / "frontend/src/views/MonitorCenter.vue").read_text(encoding="utf-8")

        for cls in [
            "sys-info-card",
            "disk-card",
            "resource-card",
            "training-card",
            "user-card",
            "timeline-chart-card",
            "timeline-ledger-card",
        ]:
            self.assertRegex(text, rf"\.{cls}\s*\{{[^}}]*padding:", cls)

    def test_views_do_not_use_ellipsis_to_hide_text(self):
        for rel in [
            "frontend/src/views/MonitorCenter.vue",
            "frontend/src/views/TaskManager.vue",
            "frontend/src/views/Dashboard.vue",
        ]:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("text-overflow: ellipsis", text, rel)


if __name__ == "__main__":
    unittest.main()
